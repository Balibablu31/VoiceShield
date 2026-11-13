"""Optional model and external-service adapters. No classifier means no score."""
import os
import shutil
import threading
from functools import lru_cache
from io import BytesIO

import httpx

_model_lock = threading.Lock()
DEFAULT_EN_MODEL = "Lennywinks/fake-news-detector-english"
DEFAULT_INDIC_MODEL = "maitry30/verilang-muril"
DEFAULT_AUDIO_MODEL = "shravan37/vaanishield-wav2vec2-asvspoof"


def detect_language(text: str, hint: str | None = None) -> str | None:
    if hint in {"en", "hi", "mr"}:
        return hint
    devanagari = sum("\u0900" <= char <= "\u097f" for char in text)
    latin = sum(char.isascii() and char.isalpha() for char in text)
    if devanagari > latin:
        return "hi/mr"  # Script is not a reliable language distinction.
    if latin:
        return "en"
    return None


@lru_cache(maxsize=8)
def _pipeline(model_id: str):
    from transformers import pipeline
    return pipeline("text-classification", model=model_id, tokenizer=model_id, device=-1)


def _fake_label(label: str, model_id: str) -> str | None:
    normalized = label.strip().lower().replace("_", "-")
    if any(token in normalized for token in ("fake", "false", "spoof", "mislead", "misinfo", "fabricat")):
        return "fake"
    if any(token in normalized for token in ("real", "true", "genuine", "authentic")):
        return "real"
    if model_id == DEFAULT_INDIC_MODEL and normalized in {"label-0", "0"}:
        return "fake"  # Checkpoint card explicitly documents Fake=0, Real=1.
    if model_id == DEFAULT_INDIC_MODEL and normalized in {"label-1", "1"}:
        return "real"
    return None


def classify_text(text: str, language: str | None) -> dict:
    if language == "en":
        model_id = os.getenv("VOICESHIELD_EN_MODEL", DEFAULT_EN_MODEL).strip()
    elif language == "mr":
        model_id = os.getenv("VOICESHIELD_MR_MODEL", DEFAULT_INDIC_MODEL).strip()
    elif language in {"hi", "hi/mr"}:
        model_id = os.getenv("VOICESHIELD_HI_MODEL", DEFAULT_INDIC_MODEL).strip()
    else:
        return {"model_status": "unsupported_language", "model_name": None, "label": "Language not supported", "confidence": None, "risk_score": None, "verdict": None,
                "summary": "Select English, Hindi, or Marathi so VoiceShield can route this text to the correct model."}
    try:
        with _model_lock:
            raw_outputs = _pipeline(model_id)(text[:12000], truncation=True, max_length=512, top_k=None)
        # Transformers versions differ: some return a flat list of label dicts,
        # others wrap that list once for a single input. Avoid indexing a dict
        # into a label string when normalizing either shape.
        if isinstance(raw_outputs, dict):
            outputs = [raw_outputs]
        elif isinstance(raw_outputs, list) and raw_outputs and isinstance(raw_outputs[0], list):
            outputs = raw_outputs[0]
        else:
            outputs = raw_outputs
        if not isinstance(outputs, list) or not all(isinstance(item, dict) for item in outputs):
            raise ValueError(f"Unexpected classifier output format: {type(raw_outputs).__name__}")
        class_scores = {}
        for item in outputs:
            mapped = _fake_label(str(item.get("label", "")), model_id)
            if mapped:
                class_scores[mapped] = float(item["score"])
        if not {"fake", "real"}.issubset(class_scores):
            raise ValueError(f"Checkpoint labels could not be mapped to fake/real: {[x.get('label') for x in outputs]}")
    except Exception as exc:
        return {"model_status": "error", "model_name": model_id, "label": "Model unavailable", "confidence": None, "risk_score": None, "verdict": None,
                "summary": f"Could not run model {model_id}: {type(exc).__name__}: {str(exc)[:180]}"}
    verdict = max(class_scores, key=class_scores.get)
    confidence = class_scores[verdict]
    return {"model_status": "ready", "model_name": model_id, "label": "Fake-pattern classification" if verdict == "fake" else "Real-pattern classification",
            "verdict": verdict, "risk_score": round(class_scores["fake"] * 100, 2), "confidence": confidence,
            "summary": f"The model classified this text as {verdict}-pattern with {confidence:.1%} confidence. This is a corpus-trained screening prediction, not proof of factual truth."}


def _audio_session(model_id: str):
    from huggingface_hub import hf_hub_download
    import onnxruntime as ort
    model_path = hf_hub_download(model_id, "voice_auth_classifier.int8.onnx")
    options = ort.SessionOptions()
    options.intra_op_num_threads = max(1, min(4, os.cpu_count() or 1))
    return ort.InferenceSession(model_path, sess_options=options, providers=["CPUExecutionProvider"])


@lru_cache(maxsize=2)
def _cached_audio_session(model_id: str):
    return _audio_session(model_id)


def _decode_audio(data: bytes):
    import av
    import numpy as np

    try:
        container = av.open(BytesIO(data))
        stream = next((item for item in container.streams if item.type == "audio"), None)
        if stream is None:
            raise ValueError("No audio stream was found in this file.")
        resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
        chunks = []
        total = 0
        for frame in container.decode(stream):
            for converted in resampler.resample(frame):
                chunk = converted.to_ndarray().reshape(-1).astype(np.float32, copy=False)
                total += chunk.size
                if total > 600 * 16000:
                    raise ValueError("Audio is longer than the 10-minute analysis limit.")
                chunks.append(chunk)
        for converted in resampler.resample(None):
            chunk = converted.to_ndarray().reshape(-1).astype(np.float32, copy=False)
            total += chunk.size
            if total > 600 * 16000:
                raise ValueError("Audio is longer than the 10-minute analysis limit.")
            chunks.append(chunk)
        container.close()
    except (av.error.InvalidDataError, av.error.FFmpegError) as exc:
        raise ValueError("The audio codec or file data could not be decoded.") from exc
    if not chunks:
        raise ValueError("The audio file contains no decodable samples.")
    audio = np.concatenate(chunks)
    if audio.size < 8000 or not np.isfinite(audio).all() or float(np.max(np.abs(audio))) < 1e-5:
        raise ValueError("Audio is empty, too short, silent, or invalid.")
    return audio


def analyze_audio_bytes(data: bytes) -> dict:
    model_id = os.getenv("VOICESHIELD_AUDIO_MODEL", DEFAULT_AUDIO_MODEL).strip()
    try:
        import numpy as np
        audio = _decode_audio(data)
        with _model_lock:
            session = _cached_audio_session(model_id)
            input_name = session.get_inputs()[0].name
            window_size, stride = 4 * 16000, 4 * 16000
            scores = []
            for start in range(0, audio.size, stride):
                window = audio[start:start + window_size]
                if window.size < 8000:
                    break
                if window.size < window_size:
                    window = np.pad(window, (0, window_size - window.size))
                logits = session.run(None, {input_name: window.astype(np.float32, copy=False)[None, :]})[0][0]
                logits = logits - np.max(logits)
                probs = np.exp(logits) / np.exp(logits).sum()
                scores.append((start / 16000, min(start + window_size, audio.size) / 16000, float(probs[1])))
        if not scores:
            raise ValueError("Audio was too short for a reliable model window.")
    except ValueError:
        raise
    except Exception as exc:
        return {"model_status": "error", "model_name": model_id, "label": "Audio model unavailable", "confidence": None,
                "risk_score": None, "verdict": None, "evidence": [], "processing_metadata": {},
                "summary": f"Could not run audio model {model_id}: {type(exc).__name__}: {str(exc)[:180]}"}
    mean_score = sum(score for _, _, score in scores) / len(scores)
    suspicious = [(start, end, score) for start, end, score in scores if score >= 0.39]
    verdict = "spoof" if mean_score >= 0.39 else "bonafide"
    evidence = [{"type": "audio_segment", "title": "Model segment prediction", "quote": f"{start:.1f}–{end:.1f}s · spoof probability {score:.1%}", "start_seconds": start, "end_seconds": end, "spoof_probability": score} for start, end, score in scores]
    evidence.append({"type": "limitation", "title": "Benchmark scope", "quote": "This community checkpoint reports ASVspoof 2019 LA results; performance on current voice cloning, telephony, noise, and other languages is not established."})
    return {"model_status": "ready", "model_name": model_id, "label": "Potential spoof" if verdict == "spoof" else "Bonafide-pattern prediction",
            "verdict": verdict, "risk_score": round(mean_score * 100, 2), "confidence": mean_score if verdict == "spoof" else 1 - mean_score,
            "evidence": evidence, "processing_metadata": {"duration_seconds": round(len(audio) / 16000, 2), "sample_rate": 16000, "segments": len(scores), "above_threshold_segments": len(suspicious)},
            "summary": f"The audio model's mean spoof probability was {mean_score:.1%} across {len(scores)} four-second segment(s). This is a screening signal, not proof of manipulation."}


async def lookup_fact_checks(query: str) -> tuple[list[dict], str]:
    key = os.getenv("GOOGLE_FACT_CHECK_API_KEY", "").strip()
    if not key:
        return [], "not_configured"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(6.0)) as client:
            response = await client.get("https://factchecktools.googleapis.com/v1alpha1/claims:search",
                                        params={"query": query[:500], "key": key, "pageSize": 5})
            response.raise_for_status()
            claims = response.json().get("claims", [])
    except (httpx.HTTPError, ValueError, TypeError):
        return [], "unavailable"
    results = []
    for claim in claims:
        for review in claim.get("claimReview", []):
            results.append({"publisher": review.get("publisher", {}).get("name", "Fact checker"),
                            "title": review.get("title", claim.get("text", "Published review")),
                            "url": review.get("url", ""), "rating": review.get("textualRating"),
                            "review_date": review.get("reviewDate")})
    return results[:8], "available" if results else "no_results"


def extract_image_text(data: bytes, language: str = "eng+hin+mar") -> tuple[str, float | None]:
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError("Pillow is unavailable. Install the backend requirements and retry.") from exc
    try:
        image = Image.open(BytesIO(data))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((2400, 2400))
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The uploaded image could not be decoded.") from exc

    executable = os.getenv("TESSERACT_CMD", "tesseract")
    if shutil.which(executable):
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = executable
            available = set(pytesseract.get_languages(config=""))
            requested = language.split("+")
            present = [code for code in requested if code in available]
            if not present:
                raise RuntimeError("Tesseract is installed but has none of the requested English/Hindi/Marathi language packs.")
            details = pytesseract.image_to_data(image, lang="+".join(present), output_type=pytesseract.Output.DICT)
            words = [w for w in details["text"] if w.strip()]
            text = " ".join(words).strip()[:12000]
            confidences = [float(c) for c, w in zip(details["conf"], details["text"]) if w.strip() and str(c).isdigit() and int(c) >= 0]
            return text, (sum(confidences) / len(confidences) / 100 if confidences else None)
        except ImportError:
            pass

    try:
        import easyocr
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("OCR is not installed. Install backend/requirements-models.txt (EasyOCR fallback) or install Tesseract with language data.") from exc
    try:
        # EasyOCR's Hindi recognition model covers Devanagari glyphs used by Hindi and Marathi.
        reader = _easyocr_reader()
        results = reader.readtext(np.asarray(image), detail=1, paragraph=False)
        text = " ".join(item[1].strip() for item in results if item[1].strip())[:12000]
        confidences = [float(item[2]) for item in results if len(item) > 2]
        return text, (sum(confidences) / len(confidences) if confidences else None)
    except Exception as exc:
        raise RuntimeError(f"EasyOCR could not process this image: {type(exc).__name__}: {str(exc)[:160]}") from exc


@lru_cache(maxsize=1)
def _easyocr_reader():
    import easyocr
    return easyocr.Reader(["en", "hi"], gpu=False, verbose=False)
