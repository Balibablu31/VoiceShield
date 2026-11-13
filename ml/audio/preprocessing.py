import librosa
import numpy as np


def load_mono_16khz(path: str, max_seconds: int = 600):
    audio, _ = librosa.load(path, sr=16000, mono=True, duration=max_seconds + 1)
    if audio.size == 0:
        raise ValueError("Audio contains no decodable samples")
    if audio.size > max_seconds * 16000:
        raise ValueError("Audio exceeds the configured duration limit")
    if not np.isfinite(audio).all() or float(np.max(np.abs(audio))) < 1e-5:
        raise ValueError("Audio is silent or contains invalid samples")
    return audio.astype(np.float32)
