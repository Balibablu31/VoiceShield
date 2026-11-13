# VoiceShield implementation status

## Audit scope

The source repository contains a React/Vite frontend and a small FastAPI/SQLAlchemy backend. The 29-page `G42 Voiceshield.pdf` synopsis was extracted and reviewed. Its core requirements are: fine-tuned wav2vec2 on ASVspoof; fine-tuned BERT/RoBERTa using LIAR and FakeNewsNet; Hindi/Marathi IndicBERT or MuRIL extension; Google Fact Check Tools cross-verification; Tesseract OCR routed into the shared text detector; evidence highlighting (audio regions and suspicious sentences); React/FastAPI/PostgreSQL architecture and persistent history. The synopsis lists live audio streaming as a stretch goal. Its functional requirements cover audio upload/recording and confidence, text/screenshot classification, automatic language routing, external reviews, OCR, and analysis history. It also calls for accuracy/EER evaluation, a risk/evidence UI, and documentation.

## Existing implementation

- React single-page UI with text, image, and audio inputs; browser recording; history list and result card.
- FastAPI endpoints for analysis, history, and basic health.
- SQLAlchemy persistence with SQLite default and PostgreSQL URL support.
- Google Fact Check Tools API lookup and local screenshot OCR (Tesseract when installed, EasyOCR otherwise).
- The prior text analyzer used hand-written wording cues and produced a fabricated-looking risk score; audio returned a fixed zero score. The prior result contract always required a score, and history discarded fact-check data.
- The frontend's operational badge did not reflect actual model/database status, and screenshot OCR was coupled to immediate analysis, preventing user review.

## Requirements and gaps

The app had all three input routes and a real external fact-check/OCR seam, but no trained model weights, model training code, language-specific routing, OCR editing stage, or detailed health contract. Audio upload only validated basic WAV decode and did not run inference. The old UI was a conventional light dashboard and called heuristic signals a risk score. The single local history store has no authentication or user isolation. No migrations or automated tests existed in the repository.

## Proposed architecture

Keep React/Vite as the client and FastAPI as the API. Keep persistence behind SQLAlchemy and route inference through optional, cached adapters. An analysis record carries separate classifier status/confidence, nullable risk score, independent published fact checks, evidence, language, and processing metadata. SQLite remains the local default; PostgreSQL uses `DATABASE_URL`. Configure models explicitly through environment variables and never infer a result from a generic encoder.

## Implemented in this phase

- Unified nullable response contract, with model status/name, confidence, language, fact-check status/results, evidence, metadata, and timestamp.
- Removed heuristic scores; integrated lazy Hugging Face text checkpoints and ONNX audio spoof inference, with explicit error responses when the model runtime or model cannot load.
- Added conservative language handling; Devanagari remains ambiguous unless the user selects Hindi or Marathi.
- Persisted fact-check results and metadata; added history type filtering and validated limits.
- Added health information for database, configured model IDs, OCR backend, and Fact Check API configuration.
- Added screenshot OCR preview, upload checks, EXIF orientation handling, English/Devanagari OCR, OCR confidence, and client-side text review before claim analysis.
- Added configured versus unconfigured status display, model confidence presentation, audio preview, and a high-contrast graphite/cyan forensic workspace treatment.
- Expanded analysis reports with source-file details, browser-calculated SHA-256 for uploaded files, and a branded PDF download generated from the persisted record. The download endpoint requires a session and enforces per-account ownership. PDF output includes only persisted model scores, evidence, audio segments, OCR metadata, and returned fact-check reviews; it does not invent missing values.
- Added a demonstration guide covering real user supplied inputs, model/API configuration, report review, persistence, and interpretation limits.
- Added account registration/login/logout with scrypt password hashes, opaque persisted sessions in HTTP-only cookies, 14-day refresh persistence, protected API routes, and per-account analysis history.
- Fixed Transformers output normalization for both flat and nested single-input results; added regression coverage for both formats.
- Refreshed the dashboard hierarchy and responsive navigation, enlarged controls and typography, simplified redundant copy, and rebuilt reports with clearly labeled, data-backed score, confidence, OCR, audio segment, provenance, and publisher-review sections.
- Added account/session tables and per-user history migration; fixed Alembic environment URL handling for isolated/custom configs.
- Added ML dependency separation and preparation/fine-tuning foundation for text plus ASVspoof protocol parsing.
- Added reusable text and wav2vec2 training/evaluation entry points; LIAR's six labels remain distinct, and audio evaluation includes EER.
- Updated configuration and run/model notes in README and `.env.example`.
- Added profile/email editing, password changes with session invalidation, one-time 30-minute password reset tokens, SMTP delivery, and password-confirmed account deletion that removes the account's active history and sessions.
- Added per-process rate limits for authentication, account recovery, contact, OCR, and analysis endpoints; security response headers; API no-store headers; and strict image MIME/signature matching.
- Added route-backed About, Help, Contact, FAQ, Privacy, Terms, Profile, and Account Settings pages plus custom not-found handling, route-aware document titles, breadcrumbs, and consistent responsive page styling.
- Added SMTP support contact requests and server-side searchable, type-filtered, sorted, paginated history, report deletion, and retry feedback.

## Deliberately deferred

- Trained VoiceShield weights, approved public checkpoint selection, dataset downloads, and performance claims.
- Sentence/token attribution and segment-level audio evidence.
- Account email verification, MFA, distributed rate limiting for multi-worker deployments, Docker deployment, and representative accuracy evaluation across the full test matrix.
- Visual verification across real mobile devices and browser microphone permissions.
- Full synopsis acceptance still requires actual trained model outputs and end-to-end evidence highlighting.

## Model status

Default public community checkpoints are configured for audio spoof screening (ASVspoof 2019 LA), English fake-news pattern classification, and Hindi/Marathi text classification. In this environment, the cached English checkpoint ran successfully through the authenticated text-analysis API against a real sentence; the API returned its model output and generated a PDF for that persisted record. This single smoke check establishes that the local English path executes, not that the output is accurate. The Hindi/Marathi and audio checkpoints were not cached and model downloads are blocked by this environment's network policy, so those real model paths could not be exercised here. No user media was available for an end-to-end OCR or audio upload smoke check. The models are community-provided, not trained or independently validated by VoiceShield. Google Fact Check publisher reviews require a user-supplied Google API key. A model classification is not a factual verdict.

## Milestone estimate

At the product feature and integration level, the project is approximately 85% complete: core analysis paths, account management, password recovery/contact integrations, account-scoped history/report management, and essential informational pages are implemented. This is an implementation-coverage estimate, not an accuracy or production-readiness claim. The final work that prevents a validated public release is VoiceShield-specific fine-tuning and evaluation on the synopsis datasets, sentence-level explainability, model smoke tests for all supported media/languages in a network-enabled environment, distributed rate limiting, email verification/MFA, and deployment hardening. No user audio or screenshot was supplied for full live-media validation.

## Verification status for this phase

- **Tested:** backend suite (24 tests) covers migrations, registration/login/logout, session persistence, profile updates, password change/reset, account deletion, ownership scoping, history search/pagination/sort/delete, contact-mail integration seam, file validation, and security headers.
- **Tested:** frontend production build and backend Python compilation.
- **Not tested against a live SMTP service:** reset email delivery and contact delivery. Mail senders are covered through controlled adapter tests; configure SMTP and perform a real inbox check before the demo.
- **Not tested in a real browser/device matrix:** route navigation and responsive behavior were reviewed in source and production build only. Test microphone permissions, keyboard behavior, and mobile browsers before public use.
- **Not tested with real audio or screenshot files in this phase:** no user media was present in the workspace. Existing API tests cover malformed uploads and explicit model-error behavior; these do not establish end-to-end model/OCR performance.
- **Security limits:** rate counters are process-local, account deletion covers the active database only (not external backups), SMTP/API secrets remain administrator-managed, and the application has not had an independent security review.

