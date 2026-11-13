# VoiceShield

**A Unified AI System for Voice Deepfake Detection and Fake News Verification** is a research-oriented application for reviewing suspicious voice recordings, claims, and screenshots. It separates model predictions from published fact-check reviews and clearly reports when a model is not configured.

## Architecture

- **Frontend:** React 18, Vite, Lucide icons, responsive CSS.
- **API:** Python 3.12 recommended, FastAPI, Pydantic, Uvicorn.
- **Persistence:** SQLAlchemy with SQLite by default; PostgreSQL via `DATABASE_URL`.
- **Integrations:** Google Fact Check Tools API for publisher reviews (API key required); Tesseract when installed, otherwise local EasyOCR.
- **Models:** public Hugging Face community checkpoints for voice spoof screening and English/Hindi/Marathi fake-pattern classification. Weights download on first use; model outputs are screening signals, not factual verdicts.

Accounts use salted scrypt password hashes and opaque, database-backed HTTP-only sessions that persist for 14 days. Analysis history is scoped to the signed-in account. Raw uploaded audio and original claim text are not stored as source fields; evidence and fact-check metadata can include excerpts/results.

## Prerequisites

- Python 3.12 (recommended; Python 3.14 is not supported by the current ML dependency stack)
- Node.js 18 or newer
- Optional: Tesseract OCR with `eng`, `hin`, and `mar` trained data
- Optional: PostgreSQL

## Run on Windows

From the repository root in PowerShell:

```powershell
cd backend
py -3.12 -m venv .venv312
.venv312\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-models.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). API docs are at `http://localhost:8000/docs`.

## Run on Linux/macOS

```bash
cd backend
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-models.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

In another terminal, `cd frontend && npm install && npm run dev`.

## Configuration

Copy `backend/.env.example` to `backend/.env`. The backend loads this file automatically; defaults use a SQLite database at `backend/voiceshield.db`. Set `DATABASE_URL` to a SQLAlchemy PostgreSQL URL for deployment and `CORS_ORIGINS` to the exact frontend origins. Use `VOICESHIELD_COOKIE_SECURE=true` when serving over HTTPS; leave it false for local HTTP development. Google Fact Check Tools requires a Google Cloud project with the API enabled and an API key; set `GOOGLE_FACT_CHECK_API_KEY` in `backend/.env`. The key stays server-side. Without it, model screening still runs and publisher fact-check lookup reports `not_configured`.

Password recovery and the contact form send email via SMTP. Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM`; set `APP_BASE_URL` to the public frontend URL so reset links point to the right host. Set `SUPPORT_EMAIL` to the support mailbox that should receive contact requests. The UI reports when mail delivery is not configured. Reset links are single-use and expire after 30 minutes. Never commit `.env` or use local HTTP / SQLite / development mail settings for a public deployment.

OCR uses local EasyOCR by default when Tesseract is absent. Its English and Hindi recognition packs are downloaded on first use; Hindi recognition covers Devanagari glyphs used by Marathi, though OCR is not a language translator. Tesseract is used if available, with its installed language packs.

## Model setup and limitations

The default checkpoints are `shravan37/vaanishield-wav2vec2-asvspoof` (audio), `Lennywinks/fake-news-detector-english` (English), and `maitry30/verilang-muril` (Hindi/Marathi). Public model files download from Hugging Face on first request and are cached locally. Python 3.12 and several GB of disk space are recommended for the model runtime/cache. No Hugging Face token is normally needed for these public repositories. Override model IDs in `backend/.env` only with compatible sequence classifiers / ONNX checkpoints and valid label mappings.

These are community checkpoints, not VoiceShield-trained or independently validated models. The audio checkpoint targets ASVspoof 2019 LA and does not establish reliability on current voice cloning, noisy/telephony audio, or other languages. The English model card does not provide independent evaluation results; the Indic model card reports its own results, which are not independently verified. A text fake-pattern score does not verify a claim. Google Fact Check results are separate publisher reviews and require the API key above.

## Training foundation

Install optional ML tooling with `pip install -r ml/requirements.txt`. See [ml/README.md](ml/README.md) for dataset schemas, ASVspoof protocol preparation, training usage, and split/label guidance. Dataset downloads and training are intentionally not started automatically. Training scripts are foundations and have not been used to produce evaluated checkpoints.

## API routes

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` — account creation, sign-in, persistent session, and sign-out.
- `PATCH /api/auth/profile`, `POST /api/auth/password`, `DELETE /api/auth/account` — profile updates, password changes, and password-confirmed account deletion.
- `POST /api/auth/password-reset/request`, `POST /api/auth/password-reset/confirm` — SMTP-delivered one-time reset links and password reset.
- `POST /api/contact` — validated support request sent to the configured support mailbox.
- `POST /api/analyze/text` — text classification adapter, language handling, fact-check lookup, and history persistence.
- `POST /api/analyze/image` — OCR followed by the text workflow.
- `POST /api/ocr` — OCR preview for user review/editing before claim submission.
- `POST /api/analyze/audio` — audio decode/resample, ONNX spoof screening, segment evidence, and history persistence.
- `GET /api/reports/{analysis_id}/pdf` — authenticated, account-scoped download of a branded PDF generated from the persisted analysis and its returned evidence.
- `GET /api/history?limit=25&skip=0&kind=text&sort=newest&q=search` — authenticated user's paginated, searchable records including fact-check results; `X-Has-More` indicates additional rows.
- `DELETE /api/history/{analysis_id}` — delete one report belonging to the signed-in user. PDF downloads are likewise owner-scoped.
- `GET /api/health` — backend, database, OCR, fact-check configuration, and model configuration status.

## Quality checks

From `backend`, run `python -m pytest`. From `frontend`, run `npm run build`. The UI uses Vite's `/api` proxy for local development. Authentication endpoints, account recovery, analysis inputs, OCR, audio, and contact requests have per-process rate limits. For multi-worker or public deployments, configure equivalent limits at a reverse proxy or shared rate-limit service; the in-process counters do not coordinate across workers or hosts. Use HTTPS, a strong SMTP credential, a PostgreSQL database with backups, exact CORS origins, and a deployment-specific secret-management process. VoiceShield is a research prototype and is not independently security-audited; representative model accuracy evaluation and deployment hardening remain necessary before consequential or public use. See [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).

For a hands-on walkthrough using your own recordings, claims, and screenshots, see [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md). Reports include source file name/type/size and SHA-256 for uploaded media when provided; this identifies the analyzed file but does not prove the file's origin or authenticity. PDF text uses built-in fonts, so non-Latin text may not render correctly in exported PDFs; the in-app report retains the original text.

