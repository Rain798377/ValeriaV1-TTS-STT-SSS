"""
Configuration - edit these values to match your setup
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ── Discord ────────────────────────────────────────────────────────────────
    DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN", "YOUR_TOKEN_HERE")
    PREFIX          = os.getenv("PREFIX", "!")

    # ── LLM (llama.cpp server) ─────────────────────────────────────────────────
    # Run: llama-server -m Dolphin3.0-Llama3.2-3B-Q4_K_M.gguf --host 127.0.0.1 --port 8080 -ngl 99
    LLAMA_API_URL   = os.getenv("LLAMA_API_URL", "http://192.9.148.110:8080")
    LLM_MAX_TOKENS  = int(os.getenv("LLM_MAX_TOKENS", "512"))
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.8"))
    SYSTEM_PROMPT   = os.getenv(
        "SYSTEM_PROMPT",
        "You are a helpful voice assistant in a Discord server. "
        "Keep responses concise and conversational — you're being read aloud. "
        "Avoid markdown, bullet points, or anything that sounds weird when spoken."
    )

    # ── STT (whisper.cpp) ──────────────────────────────────────────────────────
    # Install: pip install pywhispercpp  OR  use whisper.cpp CLI binary
    # Models: tiny, base, small, medium (small is the sweet spot for your RAM)
    WHISPER_MODEL   = os.getenv("WHISPER_MODEL", "small")
    # Set to "pywhispercpp" or "cli"
    WHISPER_BACKEND = os.getenv("WHISPER_BACKEND", "pywhispercpp")
    # Only used if WHISPER_BACKEND=cli
    WHISPER_CLI_PATH = os.getenv("WHISPER_CLI_PATH", "whisper-cli")

    # ── TTS ────────────────────────────────────────────────────────────────────
    # Options: "kokoro" or "piper"
    TTS_ENGINE      = os.getenv("TTS_ENGINE", "kokoro")

    # Kokoro settings (pip install kokoro-onnx)
    KOKORO_VOICE    = os.getenv("KOKORO_VOICE", "af_heart")  # see kokoro docs for voices
    KOKORO_SPEED    = float(os.getenv("KOKORO_SPEED", "1.0"))

    # Piper settings (faster, less natural — fallback)
    PIPER_MODEL     = os.getenv("PIPER_MODEL", "en_US-lessac-medium.onnx")
    PIPER_CLI_PATH  = os.getenv("PIPER_CLI_PATH", "piper")

    # ── Audio ──────────────────────────────────────────────────────────────────
    SAMPLE_RATE     = 16000   # whisper expects 16kHz
    SILENCE_THRESHOLD = 500   # RMS silence threshold for VAD
    SILENCE_DURATION  = 1.5   # seconds of silence before processing
    MAX_RECORD_SECS   = 30    # hard cap on recording length
