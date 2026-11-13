from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from collections import defaultdict, deque
from threading import Lock
import time
import os
import shutil

from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy import or_, text as sql_text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

load_dotenv()

from .database import Base, SessionLocal, engine
from .models import Analysis, PasswordResetToken, User, UserSession
from .mail import send_password_reset, send_support_message
from .pdf_report import render_analysis_pdf
from .schemas import (AccountDeleteRequest, AnalysisResult, ContactRequest, LoginRequest,
                      OCRResult, PasswordChangeRequest, PasswordResetConfirm,
                      PasswordResetRequest, ProfileUpdate, RegisterRequest,
                      TextRequest, UserResponse)
from .auth import hash_password, hash_session_token, new_session_token, verify_password
from .services import (DEFAULT_AUDIO_MODEL, DEFAULT_EN_MODEL, DEFAULT_INDIC_MODEL,
                       analyze_audio_bytes, classify_text, detect_language,
                       extract_image_text, lookup_fact_checks)

MAX_IMAGE_BYTES = 8_000_000
MAX_AUDIO_BYTES = 20_000_000
SESSION_COOKIE = "voiceshield_session"
SESSION_DURATION = timedelta(days=14)
RESET_DURATION = timedelta(minutes=30)
_rate_lock = Lock()
_rate_windows: dict[str, deque[float]] = defaultdict(deque)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="VoiceShield API", description="Voice deepfake and claim verification research platform", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()], allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Content-Type"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Pragma", "no-cache")
    if os.getenv("VOICESHIELD_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def enforce_rate_limit(request: Request, scope: str, maximum: int, window_seconds: int):
    client_ip = request.client.host if request.client else "unknown"
    key = f"{scope}:{client_ip}"
    now = time.monotonic()
    with _rate_lock:
        bucket = _rate_windows[key]
        while bucket and now - bucket[0] >= window_seconds:
            bucket.popleft()
        if len(bucket) >= maximum:
            retry_after = max(1, int(window_seconds - (now - bucket[0])))
            raise HTTPException(429, "Too many attempts. Please wait before trying again.", headers={"Retry-After": str(retry_after)})
        bucket.append(now)
        if len(_rate_windows) > 5000:
            expired = [k for k, values in _rate_windows.items() if not values or now - values[-1] > 3600]
            for stale_key in expired:
                _rate_windows.pop(stale_key, None)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def serialize_user(user: User) -> dict:
    return {"id": user.id, "full_name": user.full_name, "email": user.email}


def set_session_cookie(response: Response, token: str):
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=int(SESSION_DURATION.total_seconds()),
        httponly=True,
        secure=os.getenv("VOICESHIELD_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"},
        samesite="lax",
        path="/",
    )


def issue_session(db: Session, user: User, response: Response):
    token = new_session_token()
    db.add(UserSession(user_id=user.id, token_hash=hash_session_token(token), expires_at=datetime.now(timezone.utc) + SESSION_DURATION))
    db.commit()
    set_session_cookie(response, token)


def get_current_user(
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(401, "Please log in to continue.")
    session = db.query(UserSession).filter_by(token_hash=hash_session_token(token)).first()
    if not session:
        raise HTTPException(401, "Your session has expired. Please log in again.")
    expiry = session.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        raise HTTPException(401, "Your session has expired. Please log in again.")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "This account is no longer available. Please log in again.")
    return user


def persist(db: Session, data: dict) -> dict:
    row = Analysis(**data)
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "Analysis could not be saved because the database is unavailable.") from exc
    return row


def source_metadata(file: UploadFile, data: bytes) -> dict:
    filename = (file.filename or "").replace("\\", "/").split("/")[-1]
    filename = "".join(char for char in filename if char.isprintable())[:180]
    return {
        "source_filename": filename or None,
        "source_content_type": (file.content_type or "unknown")[:100],
        "source_bytes": len(data),
        "source_sha256": sha256(data).hexdigest(),
    }


async def process_text(value: str, language_hint: str, db: Session, user: User, kind="text", leading=None, metadata=None):
    detected = detect_language(value, None if language_hint == "auto" else language_hint)
    model = await run_in_threadpool(classify_text, value, detected if detected in {"en", "hi", "mr"} else None)
    checks, check_status = await lookup_fact_checks(value)
    evidence = list(leading or [])
    if detected == "hi/mr":
        evidence.append({"type": "limitation", "title": "Language needs confirmation", "quote": "Devanagari script can represent Hindi or Marathi. Select the language before relying on a language-specific model."})
    evidence.append({"type": "model_status", "title": "Classifier status", "quote": model["summary"]})
    if checks:
        evidence.append({"type": "fact_check", "title": "Independent published reviews", "quote": "Publisher ratings are shown separately from any model prediction."})
    report_metadata = {"input_characters": len(value), **(metadata or {})}
    data = {"user_id": user.id, "kind": kind, "status": "completed", "label": model["label"], "risk_score": None,
            "model_confidence": model["confidence"], "language": detected, "model_status": model["model_status"],
            "model_name": model["model_name"], "summary": model["summary"], "evidence": evidence,
            "fact_checks": checks, "fact_check_status": check_status,
            "processing_metadata": report_metadata}
    data["risk_score"] = model.get("risk_score")
    data["verdict"] = model.get("verdict")
    if model["model_status"] == "ready":
        evidence.append({"type": "classification", "title": "Classifier output", "quote": f"{model['label']} · fake-pattern score {model['risk_score']:.1f}/100 · this score is model confidence, not factual truth."})
    return persist(db, data)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(sql_text("SELECT 1"))
        database_status = "ready"
    except SQLAlchemyError:
        database_status = "unavailable"
    ocr = "tesseract" if shutil.which(os.getenv("TESSERACT_CMD", "tesseract")) else "easyocr fallback configured"
    ocr_languages = []
    if ocr == "tesseract":
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD", "tesseract")
            ocr_languages = [code for code in pytesseract.get_languages(config="") if code in {"eng", "hin", "mar"}]
        except Exception:
            ocr_languages = []
    return {"status": "ok", "database": database_status, "models": {"audio": "configured", "audio_model_id": os.getenv("VOICESHIELD_AUDIO_MODEL", DEFAULT_AUDIO_MODEL), "english": "configured", "english_model_id": os.getenv("VOICESHIELD_EN_MODEL", DEFAULT_EN_MODEL), "multilingual": {"hi": "configured", "mr": "configured"}, "multilingual_model_id": os.getenv("VOICESHIELD_HI_MODEL", DEFAULT_INDIC_MODEL)}, "ocr": ocr, "ocr_languages": ocr_languages,
            "fact_check": "configured" if os.getenv("GOOGLE_FACT_CHECK_API_KEY") else "not_configured"}


@app.post("/api/auth/register", response_model=UserResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_rate_limit(request, "register", 5, 3600)
    if db.query(User).filter_by(email=payload.email).first():
        raise HTTPException(409, "An account with this email already exists.")
    first_account = db.query(User).count() == 0
    user = User(full_name=payload.full_name, email=payload.email, password_hash=hash_password(payload.password))
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        if first_account:
            # Preserve legacy installation history by assigning it once to its first owner.
            db.query(Analysis).filter(Analysis.user_id.is_(None)).update({Analysis.user_id: user.id})
            db.commit()
        issue_session(db, user, response)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "Account creation failed because the database is unavailable.") from exc
    return serialize_user(user)


@app.post("/api/auth/login", response_model=UserResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_rate_limit(request, "login", 10, 900)
    user = db.query(User).filter_by(email=payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    issue_session(db, user, response)
    return serialize_user(user)


@app.get("/api/auth/me", response_model=UserResponse)
def current_account(user: User = Depends(get_current_user)):
    return serialize_user(user)


@app.patch("/api/auth/profile", response_model=UserResponse)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user.full_name = payload.full_name
    user.email = payload.email
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "Your profile could not be saved because the database is unavailable.") from exc
    return serialize_user(user)


@app.post("/api/auth/password")
def change_password(payload: PasswordChangeRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(400, "Your current password is incorrect.")
    user.password_hash = hash_password(payload.new_password)
    token = request.cookies.get(SESSION_COOKIE)
    current_hash = hash_session_token(token) if token else ""
    db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.token_hash != current_hash).delete(synchronize_session=False)
    db.commit()
    return {"status": "password_updated"}


@app.post("/api/auth/password-reset/request", status_code=202)
def request_password_reset(payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request, "password-reset", 5, 3600)
    if not os.getenv("SMTP_HOST", "").strip() or not os.getenv("SMTP_FROM", "").strip():
        raise HTTPException(503, "Password recovery email is not configured. Set SMTP_HOST and SMTP_FROM in backend/.env.")
    user = db.query(User).filter_by(email=payload.email).first()
    if user:
        raw_token = new_session_token()
        db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete(synchronize_session=False)
        db.add(PasswordResetToken(user_id=user.id, token_hash=hash_session_token(raw_token),
                                  expires_at=datetime.now(timezone.utc) + RESET_DURATION))
        db.commit()
        try:
            send_password_reset(user.email, raw_token)
        except (OSError, RuntimeError, ValueError) as exc:
            db.query(PasswordResetToken).filter_by(user_id=user.id).delete(synchronize_session=False)
            db.commit()
            raise HTTPException(503, "The password reset email could not be sent. Check the SMTP settings and try again.") from exc
    return {"message": "If an account exists for that address, password reset instructions have been sent."}


@app.post("/api/auth/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    reset = db.query(PasswordResetToken).filter_by(token_hash=hash_session_token(payload.token)).first()
    if not reset:
        raise HTTPException(400, "This password reset link is invalid or has already been used.")
    expires_at = reset.expires_at if reset.expires_at.tzinfo else reset.expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        db.delete(reset)
        db.commit()
        raise HTTPException(400, "This password reset link has expired. Request a new one.")
    user = db.get(User, reset.user_id)
    if not user:
        db.delete(reset)
        db.commit()
        raise HTTPException(400, "This password reset link is invalid or has already been used.")
    user.password_hash = hash_password(payload.new_password)
    db.query(UserSession).filter_by(user_id=user.id).delete(synchronize_session=False)
    db.query(PasswordResetToken).filter_by(user_id=user.id).delete(synchronize_session=False)
    db.commit()
    return {"status": "password_reset"}


@app.delete("/api/auth/account", status_code=204)
def delete_account(payload: AccountDeleteRequest, response: Response, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(400, "The password was not correct. Your account has not been deleted.")
    db.query(Analysis).filter_by(user_id=user.id).delete(synchronize_session=False)
    db.query(UserSession).filter_by(user_id=user.id).delete(synchronize_session=False)
    db.query(PasswordResetToken).filter_by(user_id=user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    response.status_code = 204
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="lax")
    return response


@app.post("/api/contact", status_code=202)
def contact_support(payload: ContactRequest, request: Request):
    enforce_rate_limit(request, "contact", 3, 3600)
    if not os.getenv("SUPPORT_EMAIL", "").strip():
        raise HTTPException(503, "Support email is not configured. Set SUPPORT_EMAIL in backend/.env.")
    try:
        send_support_message(payload.full_name, payload.email, payload.message)
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(503, "Your message could not be delivered. Please try again later.") from exc
    return {"message": "Your message was sent to the VoiceShield support team."}


@app.post("/api/auth/logout")
def logout(response: Response, token: str | None = Cookie(default=None, alias=SESSION_COOKIE), db: Session = Depends(get_db)):
    if token:
        session = db.query(UserSession).filter_by(token_hash=hash_session_token(token)).first()
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="lax")
    return {"status": "logged_out"}


@app.post("/api/analyze/text", response_model=AnalysisResult)
async def analyze_text_route(payload: TextRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    enforce_rate_limit(request, "analyze-text", 30, 600)
    leading = []
    metadata = {}
    if payload.kind == "image":
        leading = [{"type": "ocr", "title": "User-reviewed screenshot text", "quote": payload.text[:400]}, {"type": "ocr_metadata", "title": "OCR confidence", "quote": f"{payload.ocr_confidence:.0%}" if payload.ocr_confidence is not None else "Unavailable"}]
        metadata = {"ocr_confidence": payload.ocr_confidence, "source_filename": payload.source_filename,
                    "source_content_type": payload.source_content_type, "source_bytes": payload.source_bytes,
                    "source_sha256": payload.source_sha256}
    return await process_text(payload.text, payload.language, db, user=user, kind=payload.kind, leading=leading, metadata=metadata)


async def read_limited(file: UploadFile, limit: int) -> bytes:
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File exceeds the {limit // 1_000_000} MB limit.")
    if not data:
        raise HTTPException(422, "The uploaded file is empty.")
    return data


def validate_image_bytes(data: bytes, content_type: str):
    valid = ((content_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"))
             or (content_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff"))
             or (content_type == "image/webp" and len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"))
    if not valid:
        raise HTTPException(415, "The file content does not match a supported PNG, JPEG, or WebP image.")


async def ocr_upload(data: bytes, language: str):
    tesseract_languages = {"en": "eng", "hi": "hin", "mr": "mar", "auto": "eng+hin+mar"}[language]
    try:
        return await run_in_threadpool(extract_image_text, data, tesseract_languages)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/ocr", response_model=OCRResult)
async def ocr_preview(request: Request, file: UploadFile = File(...), language: str = Form("auto"), user: User = Depends(get_current_user)):
    enforce_rate_limit(request, "ocr", 15, 600)
    if language not in {"en", "hi", "mr", "auto"}:
        raise HTTPException(422, "Language must be en, hi, mr, or auto.")
    if file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(415, "Upload a PNG, JPEG, or WebP screenshot.")
    data = await read_limited(file, MAX_IMAGE_BYTES)
    validate_image_bytes(data, file.content_type)
    extracted, confidence = await ocr_upload(data, language)
    return {"text": extracted, "language": language if language != "auto" else detect_language(extracted), "status": "completed" if extracted else "no_text", "confidence": confidence}


@app.post("/api/analyze/image", response_model=AnalysisResult)
async def analyze_image(request: Request, file: UploadFile = File(...), language: str = Form("auto"), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    enforce_rate_limit(request, "analyze-image", 10, 600)
    if file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(415, "Upload a PNG, JPEG, or WebP screenshot.")
    data = await read_limited(file, MAX_IMAGE_BYTES)
    validate_image_bytes(data, file.content_type)
    if language not in {"en", "hi", "mr", "auto"}:
        raise HTTPException(422, "Language must be en, hi, mr, or auto.")
    extracted, confidence = await ocr_upload(data, language)
    if len(extracted.strip()) < 8:
        raise HTTPException(422, "OCR could not find enough readable text in the image.")
    return await process_text(extracted, language if language in {"en", "hi", "mr", "auto"} else "auto", db, user=user, kind="image",
        leading=[{"type": "ocr", "title": "Text extracted from screenshot", "quote": extracted[:400]}, {"type": "ocr_metadata", "title": "OCR confidence", "quote": f"{confidence:.0%}" if confidence is not None else "Unavailable"}],
        metadata={"ocr_confidence": confidence, **source_metadata(file, data)})


@app.post("/api/analyze/audio", response_model=AnalysisResult)
async def analyze_audio(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    enforce_rate_limit(request, "analyze-audio", 10, 600)
    allowed = {"audio/wav", "audio/x-wav", "audio/wave", "audio/mpeg", "audio/mp4", "audio/x-m4a", "audio/webm", "audio/ogg", "audio/flac", "application/octet-stream"}
    if file.content_type not in allowed:
        raise HTTPException(415, "Upload WAV, MP3, M4A, WebM, OGG, or FLAC audio.")
    data = await read_limited(file, MAX_AUDIO_BYTES)
    wav_file = data.startswith(b"RIFF") and data[8:12] == b"WAVE"
    recognized = (wav_file or data.startswith((b"ID3", b"OggS", b"fLaC", b"\x1aE\xdf\xa3"))
                  or data[4:8] == b"ftyp" or (len(data) > 1 and data[0] == 0xff and data[1] & 0xe0 == 0xe0))
    if not recognized:
        raise HTTPException(415, "The file content does not match a supported audio format.")
    try:
        result = await run_in_threadpool(analyze_audio_bytes, data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return persist(db, {"user_id": user.id, "kind": "audio", "status": "completed", "label": result["label"], "risk_score": result["risk_score"],
        "model_confidence": result["confidence"], "language": None, "model_status": result["model_status"], "model_name": result["model_name"],
        "summary": result["summary"], "evidence": result["evidence"], "fact_checks": [], "fact_check_status": "not_applicable",
        "processing_metadata": {**result["processing_metadata"], **source_metadata(file, data), "bytes_received": len(data)}, "verdict": result["verdict"]})


@app.get("/api/history", response_model=list[AnalysisResult])
def history(response: Response, limit: int = 25, skip: int = 0, kind: str | None = None, sort: str = "newest", q: str = "",
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if limit < 1 or limit > 100:
        raise HTTPException(422, "limit must be between 1 and 100.")
    if skip < 0 or skip > 1_000_000:
        raise HTTPException(422, "skip must be between 0 and 1000000.")
    if sort not in {"newest", "oldest"}:
        raise HTTPException(422, "sort must be newest or oldest.")
    if len(q) > 120:
        raise HTTPException(422, "Search text must be 120 characters or less.")
    query = db.query(Analysis).filter(Analysis.user_id == user.id)
    if kind in {"audio", "text", "image"}:
        query = query.filter(Analysis.kind == kind)
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(Analysis.label.ilike(pattern), Analysis.summary.ilike(pattern)))
    ordering = Analysis.created_at.asc() if sort == "oldest" else Analysis.created_at.desc()
    rows = query.order_by(ordering, Analysis.id.asc() if sort == "oldest" else Analysis.id.desc()).offset(skip).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    if response is not None:
        response.headers["X-Has-More"] = "true" if has_more else "false"
    return rows


@app.delete("/api/history/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.query(Analysis).filter_by(id=analysis_id, user_id=user.id).first()
    if not row:
        raise HTTPException(404, "Investigation report not found.")
    db.delete(row)
    db.commit()
    return Response(status_code=204)


@app.get("/api/reports/{analysis_id}/pdf")
def download_report_pdf(analysis_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = db.query(Analysis).filter(Analysis.id == analysis_id, Analysis.user_id == user.id).first()
    if not record:
        raise HTTPException(404, "Investigation report not found.")
    pdf = render_analysis_pdf(record)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="VoiceShield-Report-{analysis_id}.pdf"'})
