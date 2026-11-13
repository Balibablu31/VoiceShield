from io import BytesIO
import wave

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.database import Base


@pytest.fixture
def client(monkeypatch):
    main._rate_windows.clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    def override_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()
    main.app.dependency_overrides[main.get_db] = override_db
    monkeypatch.setattr(main, "classify_text", lambda text, lang: {"model_status":"not_configured","model_name":None,"label":"Model not configured","confidence":None,"summary":"No classifier configured."})
    async def no_checks(query): return [], "not_configured"
    monkeypatch.setattr(main, "lookup_fact_checks", no_checks)
    with TestClient(main.app) as test_client:
        response = test_client.post("/api/auth/register", json={"full_name":"Test User", "email":"test@example.com", "password":"correct horse battery"})
        assert response.status_code == 201
        yield test_client
    main.app.dependency_overrides.clear()
    main._rate_windows.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_health_reports_default_model_checkpoints(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["models"]["audio"] == "configured"
    assert response.json()["models"]["audio_model_id"] == "shravan37/vaanishield-wav2vec2-asvspoof"


def test_authentication_is_required_and_session_persists(client):
    assert client.get("/api/auth/me").json()["email"] == "test@example.com"
    assert client.get("/api/history").status_code == 200
    token = client.cookies.get("voiceshield_session")
    with TestClient(main.app) as refreshed_client:
        refreshed_client.cookies.set("voiceshield_session", token)
        assert refreshed_client.get("/api/auth/me").status_code == 200
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/history").status_code == 401
    assert client.post("/api/analyze/text", json={"text":"A sufficiently long claim for review.", "language":"en"}).status_code == 401


def test_register_login_duplicate_and_logout(client):
    payload = {"full_name":"Second User", "email":"second@example.com", "password":"correct horse battery"}
    registered = client.post("/api/auth/register", json=payload)
    assert registered.status_code == 201
    cookie = registered.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "max-age=1209600" in cookie
    assert client.post("/api/auth/register", json=payload).status_code == 409
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email":"second@example.com", "password":"wrong password"}).status_code == 401
    assert client.post("/api/auth/login", json={"email":"second@example.com", "password":payload["password"]}).status_code == 200


def test_registration_validates_email_and_password(client):
    assert client.post("/api/auth/register", json={"full_name":"Bad", "email":"not-an-email", "password":"correct horse battery"}).status_code == 422
    assert client.post("/api/auth/register", json={"full_name":"Bad", "email":"bad@example.com", "password":"short"}).status_code == 422


def test_users_cannot_read_each_others_analysis_history(client):
    first_report = client.post("/api/analyze/text", json={"text":"A sufficiently long claim for review.", "language":"en"}).json()
    assert client.get(f"/api/reports/{first_report['id']}/pdf").status_code == 200
    client.post("/api/auth/logout")
    response = client.post("/api/auth/register", json={"full_name":"Other User", "email":"other@example.com", "password":"correct horse battery"})
    assert response.status_code == 201
    assert client.get("/api/history").json() == []
    assert client.get(f"/api/reports/{first_report['id']}/pdf").status_code == 404
    assert client.delete(f"/api/history/{first_report['id']}").status_code == 404


def test_pdf_report_contains_analysis_and_download_headers(client):
    analysis = client.post("/api/analyze/text", json={"text":"A sufficiently long claim for report export.", "language":"en"}).json()
    response = client.get(f"/api/reports/{analysis['id']}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment; filename=\"VoiceShield-Report-" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-1.4") and response.content.rstrip().endswith(b"%%EOF")
    assert f"RECORD VS-{analysis['id']:06d}".encode() in response.content
    assert b"Findings and evidence" in response.content


def test_screenshot_report_preserves_ocr_and_file_provenance(client):
    digest = "a" * 64
    analysis = client.post("/api/analyze/text", json={
        "text": "A sufficiently long screenshot claim for review.", "language": "en", "kind": "image",
        "ocr_confidence": 0.91, "source_filename": "article.png", "source_content_type": "image/png",
        "source_sha256": digest, "source_bytes": 12345,
    }).json()
    assert analysis["processing_metadata"]["source_sha256"] == digest
    assert analysis["processing_metadata"]["ocr_confidence"] == 0.91
    pdf = client.get(f"/api/reports/{analysis['id']}/pdf")
    assert pdf.status_code == 200
    assert b"article.png" in pdf.content and digest.encode() in pdf.content
    assert b"SCREENSHOT CLAIM ANALYSIS" in pdf.content


def test_text_result_uses_null_scores_and_persists(client):
    response = client.post("/api/analyze/text", json={"text":"A sufficiently long claim for review.", "language":"en"})
    assert response.status_code == 200
    data = response.json()
    assert data["model_status"] == "not_configured"
    assert data["risk_score"] is None and data["model_confidence"] is None
    assert client.get("/api/history").json()[0]["fact_checks"] == []


def test_fact_check_results_survive_history_retrieval(client, monkeypatch):
    async def checks(query):
        return [{"publisher":"Verifier","title":"Review title","url":"https://example.test/review","rating":"False","review_date":"2026-01-01"}], "available"
    monkeypatch.setattr(main, "lookup_fact_checks", checks)
    response = client.post("/api/analyze/text", json={"text":"A sufficiently long claim for review.", "language":"en"})
    assert response.json()["fact_checks"][0]["publisher"] == "Verifier"
    assert client.get("/api/history").json()[0]["fact_checks"][0]["rating"] == "False"


def test_blank_and_short_text_rejected(client):
    assert client.post("/api/analyze/text", json={"text":"   "}).status_code == 422
    assert client.post("/api/analyze/text", json={"text":"short"}).status_code == 422


def test_unsupported_image_rejected(client):
    response = client.post("/api/analyze/image", files={"file":("bad.gif", b"GIF89a", "image/gif")})
    assert response.status_code == 415


def test_image_mime_must_match_file_signature(client):
    response = client.post("/api/analyze/image", files={"file":("fake.png", b"GIF89a", "image/png")})
    assert response.status_code == 415


def test_unsupported_audio_rejected(client):
    response = client.post("/api/analyze/audio", files={"file":("clip.exe", b"no", "application/x-msdownload")})
    assert response.status_code == 415


def test_audio_with_missing_runtime_returns_explicit_error(client, monkeypatch):
    monkeypatch.setitem(main.analyze_audio_bytes.__globals__, "_cached_audio_session", lambda model_id: (_ for _ in ()).throw(RuntimeError("model runtime unavailable")))
    data = BytesIO()
    with wave.open(data, "wb") as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(16000); stream.writeframes(b"\x01\0" * 16000)
    response = client.post("/api/analyze/audio", files={"file":("sample.wav", data.getvalue(), "audio/wav")})
    assert response.status_code == 200
    assert response.json()["model_status"] == "error"
    assert response.json()["model_confidence"] is None and response.json()["risk_score"] is None


def test_history_limit_validation(client):
    assert client.get("/api/history?limit=1000").status_code == 422


def test_profile_password_and_session_management(client):
    created = client.post("/api/auth/register", json={"full_name":"Second User", "email":"second@example.com", "password":"correct horse battery"})
    assert created.status_code == 201
    profile = client.patch("/api/auth/profile", json={"full_name":"Updated User", "email":"updated@example.com"})
    assert profile.status_code == 200 and profile.json()["email"] == "updated@example.com"
    assert client.get("/api/auth/me").json()["full_name"] == "Updated User"
    assert client.patch("/api/auth/profile", json={"full_name":"Other", "email":"test@example.com"}).status_code == 409
    assert client.post("/api/auth/password", json={"current_password":"wrong password", "new_password":"new secure password"}).status_code == 400
    changed = client.post("/api/auth/password", json={"current_password":"correct horse battery", "new_password":"new secure password"})
    assert changed.status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.post("/api/auth/login", json={"email":"updated@example.com", "password":"correct horse battery"}).status_code == 401
    assert client.post("/api/auth/login", json={"email":"updated@example.com", "password":"new secure password"}).status_code == 200


def test_password_reset_is_one_time_and_revokes_sessions(client, monkeypatch):
    issued = []
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "no-reply@example.test")
    monkeypatch.setattr(main, "send_password_reset", lambda email, token: issued.append((email, token)))
    response = client.post("/api/auth/password-reset/request", json={"email":"test@example.com"})
    assert response.status_code == 202 and len(issued) == 1
    raw_token = issued[0][1]
    assert main.hash_session_token(raw_token) != raw_token
    reset = client.post("/api/auth/password-reset/confirm", json={"token":raw_token, "new_password":"reset secure password"})
    assert reset.status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/password-reset/confirm", json={"token":raw_token, "new_password":"another secure password"}).status_code == 400
    assert client.post("/api/auth/login", json={"email":"test@example.com", "password":"reset secure password"}).status_code == 200


def test_reset_request_is_generic_for_unknown_account(client, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "no-reply@example.test")
    monkeypatch.setattr(main, "send_password_reset", lambda email, token: None)
    response = client.post("/api/auth/password-reset/request", json={"email":"nobody@example.com"})
    assert response.status_code == 202
    assert "If an account exists" in response.json()["message"]


def test_account_deletion_removes_history_and_session(client):
    report = client.post("/api/analyze/text", json={"text":"A saved investigation that will be deleted.", "language":"en"}).json()
    assert client.get("/api/history").json()
    response = client.request("DELETE", "/api/auth/account", json={"password":"correct horse battery"})
    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/reports/%s/pdf" % report["id"]).status_code == 401


def test_history_pagination_search_sort_and_delete(client):
    older = client.post("/api/analyze/text", json={"text":"A claim about rainfall in a test report.", "language":"en"}).json()
    newer = client.post("/api/analyze/text", json={"text":"Another unrelated report with a long claim.", "language":"en"}).json()
    page = client.get("/api/history?limit=1&skip=0&sort=oldest")
    assert page.status_code == 200 and page.headers["x-has-more"] == "true"
    assert page.json()[0]["id"] == older["id"]
    filtered = client.get("/api/history?q=Model%20not%20configured")
    assert len(filtered.json()) == 2 and {row["id"] for row in filtered.json()} == {older["id"], newer["id"]}
    assert client.delete(f"/api/history/{newer['id']}").status_code == 204
    assert all(row["id"] != newer["id"] for row in client.get("/api/history").json())


def test_contact_support_uses_configured_mailer(client, monkeypatch):
    sent = []
    monkeypatch.setenv("SUPPORT_EMAIL", "support@example.test")
    monkeypatch.setattr(main, "send_support_message", lambda name, email, message: sent.append((name, email, message)))
    response = client.post("/api/contact", json={"full_name":"Demo User", "email":"demo@example.test", "message":"I need help with a report export."})
    assert response.status_code == 202 and sent[0][1] == "demo@example.test"


def test_api_sets_security_headers(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_login_rate_limit_returns_retry_after(client):
    for _ in range(10):
        assert client.post("/api/auth/login", json={"email":"test@example.com", "password":"incorrect password"}).status_code == 401
    limited = client.post("/api/auth/login", json={"email":"test@example.com", "password":"incorrect password"})
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
