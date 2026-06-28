"""
STT — Speech to Text via whisper.cpp (pywhispercpp)

Handles resampling from Discord's 48kHz WAV to Whisper's required 16kHz.
"""

import io
import os
import tempfile
import wave
import struct

from config import Config

_whisper_model = None

def _load_whisper():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    try:
        from pywhispercpp.model import Model
        print(f"[STT] Loading Whisper model: {Config.WHISPER_MODEL}")
        _whisper_model = Model(Config.WHISPER_MODEL, print_realtime=False, print_progress=False)
        print("[STT] Whisper model loaded")
        return _whisper_model
    except ImportError:
        raise RuntimeError("pywhispercpp not installed. Run: pip install pywhispercpp")


def _resample_wav_to_16k(wav_bytes: bytes) -> bytes:
    """
    Convert any WAV (typically 48kHz stereo from Discord) to 16kHz mono
    which is what Whisper requires.
    """
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, 'rb') as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    # Already correct
    if framerate == 16000 and channels == 1:
        return wav_bytes

    # Convert to int16 samples
    if sampwidth == 2:
        fmt = f"<{len(frames)//2}h"
        samples = list(struct.unpack(fmt, frames))
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth}")

    # Stereo -> mono (average channels)
    if channels == 2:
        mono = []
        for i in range(0, len(samples), 2):
            avg = (samples[i] + samples[i+1]) // 2
            mono.append(avg)
        samples = mono
    elif channels > 2:
        # Take first channel only
        samples = samples[::channels]

    # Resample to 16kHz using linear interpolation
    if framerate != 16000:
        ratio = 16000 / framerate
        new_length = int(len(samples) * ratio)
        resampled = []
        for i in range(new_length):
            src = i / ratio
            idx = int(src)
            frac = src - idx
            if idx + 1 < len(samples):
                val = int(samples[idx] * (1 - frac) + samples[idx + 1] * frac)
            else:
                val = samples[idx] if idx < len(samples) else 0
            resampled.append(max(-32768, min(32767, val)))
        samples = resampled

    # Pack back to bytes
    packed = struct.pack(f"<{len(samples)}h", *samples)

    # Write new WAV
    out = io.BytesIO()
    with wave.open(out, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(packed)

    return out.getvalue()


def transcribe_audio(wav_bytes: bytes) -> str:
    """Transcribe WAV audio bytes to text."""
    if not wav_bytes or len(wav_bytes) < 1000:
        return ""

    try:
        # Resample to 16kHz mono
        wav_16k = _resample_wav_to_16k(wav_bytes)

        model = _load_whisper()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_16k)
            tmp_path = tmp.name

        try:
            segments = model.transcribe(tmp_path)
            text = " ".join(seg.text for seg in segments).strip()
        finally:
            os.unlink(tmp_path)

        print(f"[STT] Transcript: {text!r}")
        return text

    except Exception as e:
        print(f"[STT] Error: {e}")
        return ""