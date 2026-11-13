# VoiceShield demonstration guide

This guide exercises the live integrations. It contains input suggestions only; VoiceShield's outputs depend on the configured checkpoints, source API responses, and the files you submit. Do not treat a model prediction as ground truth.

## Before the demo

1. Start the backend and frontend using the commands in the root README.
2. Confirm `GET /api/health` reports database availability and shows which model checkpoints, OCR backend, and Google Fact Check API are configured.
3. Register a demo account and sign in. Keep the backend model dependencies installed and allow the first request to download/cache the selected public checkpoints and OCR language packs.
4. For published fact-check reviews, configure `GOOGLE_FACT_CHECK_API_KEY` in `backend/.env` and restart the API. Without the key, text and screenshot model analysis can still run, while publisher lookup reports `not_configured`.

## Voice Check

1. Select Voice Check and record a short spoken sentence or upload an audio file supported by the current decoder (WAV is the safest choice for a demo).
2. Review the recording preview and submit it.
3. Inspect model status, the returned score/confidence when available, segment scores, processing metadata, and limitations. An unavailable checkpoint or unsupported/undecodable file should appear as an explicit error/status without an invented score.
4. Download the PDF and compare its analysis ID, source details, model metadata, and segment outputs with the in-app report.

## Text Claim Verification

1. Submit a complete, attributable claim from a current news article or public statement. For the fact-check integration demo, choose a claim that has a published review and configure the Google API key beforehand.
2. Select the claim language when the automatic detector is ambiguous, particularly for Devanagari text.
3. Review the model screening output separately from publisher review records. Open any returned publisher link to inspect the original review; no match is not confirmation of truth.
4. Download the PDF and verify that it preserves only the returned score, evidence, and review records.

## Screenshot Analysis

1. Use a screenshot containing legible text from a real article, public notice, or claim. Avoid sensitive personal data.
2. Review the OCR preview, adjust the recognized text if needed, and submit the claim for the shared text-analysis workflow.
3. Inspect OCR confidence and recognized-text evidence alongside the downstream text result. The current image workflow analyzes OCR text and does not detect pixel-level image editing or synthetic image generation.
4. Download the report and verify its source filename/type/size/hash and OCR findings.

## Persistence and access checks

- Refresh after login: the session should persist. Sign out, then refresh and verify protected history/reports are no longer available until signing in again.
- Run one analysis of each type and confirm it appears in the account's history after a refresh.
- Try to open one report download while signed out: the API should reject it. Reports are scoped to the account that created the analysis.
- Record the model IDs and statuses from the report and health endpoint. A configured checkpoint does not mean its accuracy has been validated for your use case.

## What the report establishes

The report records what this installation returned at analysis time, the model/check status, applicable provenance, and pipeline limitations. Scores from community checkpoints are screening signals, not proof that a voice is real/fake or that a claim is true/false. For an academic performance demonstration, use held-out labeled data and report measured metrics (for example EER for voice); do not infer accuracy from a handful of examples.
