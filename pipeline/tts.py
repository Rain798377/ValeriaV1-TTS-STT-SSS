"""
TTS — Text to Speech

Supports two engines:
  - kokoro:  kokoro-onnx (higher quality, 82M params, ~300MB)
             pip install kokoro-onnx
  - piper:   Piper TTS (faster, smaller, less natural)
             https://github.com/rhasspy/piper

Input:  text string
Output: path to a temporary WAV file (caller should clean up after playing)
"""

import os
import subprocess
import tempfile

from config import Config

# ── Kokoro backend ─────────────────────────────────────────────────────────────

_kokoro_model = None

def _load_kokoro():
    global _kokoro_model
    if _kokoro_model is not None:
        return _kokoro_model
    try:
        from kokoro_onnx import Kokoro
        print("[TTS] Loading Kokoro model...")
        _kokoro_model = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
        print("[TTS] Kokoro loaded")
        return _kokoro_model
    except ImportError:
        raise RuntimeError(
            "kokoro-onnx not installed. Run: pip install kokoro-onnx\n"
            "Then download models from: https://github.com/thewh1teagle/kokoro-onnx/releases"
        )


def _synthesize_kokoro(text: str) -> str:
    """Returns path to a temp WAV file."""
    import soundfile as sf
    import numpy as np

    kokoro = _load_kokoro()

    samples, sample_rate = kokoro.create(
        text,
        voice=Config.KOKORO_VOICE,
        speed=Config.KOKORO_SPEED,
        lang="en-us",
    )

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, samples, sample_rate)
    return tmp.name


# ── Piper backend ──────────────────────────────────────────────────────────────

def _synthesize_piper(text: str) -> str:
    """Returns path to a temp WAV file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()

    try:
        proc = subprocess.run(
            [
                Config.PIPER_CLI_PATH,
                "--model", Config.PIPER_MODEL,
                "--output_file", tmp.name,
            ],
            input=text,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            print(f"[TTS/Piper] Error: {proc.stderr}")
            return None
        return tmp.name

    except FileNotFoundError:
        raise RuntimeError(
            f"piper not found at '{Config.PIPER_CLI_PATH}'. "
            "Download from https://github.com/rhasspy/piper/releases"
        )


# ── Public API ─────────────────────────────────────────────────────────────────

def synthesize_speech(text: str) -> str | None:
    """
    Convert text to speech and return the path to a WAV file.
    The caller is responsible for deleting the file after playback.
    Returns None on failure.
    """
    if not text or not text.strip():
        return None

    # Clean text for TTS (remove things that sound bad when read aloud)
    text = _clean_for_tts(text)

    try:
        if Config.TTS_ENGINE == "piper":
            path = _synthesize_piper(text)
        else:
            path = _synthesize_kokoro(text)

        print(f"[TTS] Synthesized to: {path}")
        return path

    except Exception as e:
        print(f"[TTS] Error: {e}")
        return None


def _clean_for_tts(text: str) -> str:
    """Remove markdown and other artifacts that sound bad when read aloud."""
    import re
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)   # bold/italic
    text = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", text)      # code
    text = re.sub(r"#{1,6}\s*", "", text)                  # headers
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)        # links
    text = re.sub(r"_{1,2}(.+?)_{1,2}", r"\1", text)       # underline
    text = text.strip()
    return text
