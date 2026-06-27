"""
STT — Speech to Text via whisper.cpp

Supports two backends:
  - pywhispercpp: Python bindings (recommended, no subprocess)
  - cli:          whisper-cli binary (fallback)

Input:  WAV bytes (16kHz mono int16)
Output: Transcribed string
"""

import io
import os
import subprocess
import tempfile
import wave

from config import Config

# ── pywhispercpp backend ───────────────────────────────────────────────────────

_whisper_model = None

def _load_whisper():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    try:
        from pywhispercpp.model import Model
        print(f"[STT] Loading Whisper model: {Config.WHISPER_MODEL}")
        _whisper_model = Model(Config.WHISPER_MODEL, print_realtime=False, print_progress=False)
        print("[STT] Whisper model loaded ✅")
        return _whisper_model
    except ImportError:
        raise RuntimeError(
            "pywhispercpp not installed. Run: pip install pywhispercpp\n"
            "Or set WHISPER_BACKEND=cli in your .env"
        )


def _transcribe_pywhispercpp(wav_bytes: bytes) -> str:
    model = _load_whisper()

    # Write WAV to a temp file — pywhispercpp reads from disk
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name

    try:
        segments = model.transcribe(tmp_path)
        return " ".join(seg.text for seg in segments).strip()
    finally:
        os.unlink(tmp_path)


# ── CLI backend ────────────────────────────────────────────────────────────────

def _transcribe_cli(wav_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                Config.WHISPER_CLI_PATH,
                "-m", f"models/ggml-{Config.WHISPER_MODEL}.bin",
                "-f", tmp_path,
                "--output-txt",
                "--no-timestamps",
                "-nt",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError(
            f"whisper-cli not found at '{Config.WHISPER_CLI_PATH}'. "
            "Build whisper.cpp or set WHISPER_CLI_PATH in .env"
        )
    finally:
        os.unlink(tmp_path)


# ── Public API ─────────────────────────────────────────────────────────────────

def transcribe_audio(wav_bytes: bytes) -> str:
    """
    Transcribe WAV audio bytes to text.
    Automatically uses the configured backend.
    """
    if not wav_bytes or len(wav_bytes) < 1000:
        return ""

    try:
        if Config.WHISPER_BACKEND == "cli":
            text = _transcribe_cli(wav_bytes)
        else:
            text = _transcribe_pywhispercpp(wav_bytes)

        print(f"[STT] Transcript: {text!r}")
        return text

    except Exception as e:
        print(f"[STT] Error: {e}")
        return ""
