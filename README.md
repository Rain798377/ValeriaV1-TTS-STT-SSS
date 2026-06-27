# Discord Voice Bot

A local, fully offline Discord voice bot. Listens to voice → transcribes → LLM response → speaks back.

```
User speaks → Whisper (STT) → llama.cpp (LLM) → Kokoro/Piper (TTS) → Bot speaks
```

Designed to run on a **4GB VRAM / 32GB RAM** system alongside a GGUF model.

---

## Requirements

- Python 3.11+
- `ffmpeg` installed and on PATH
- A Discord bot token
- `llama-server` from [llama.cpp](https://github.com/ggerganov/llama.cpp) running locally
- A GGUF model (see recommendations below)

---

## Setup

### 1. Clone and install

```bash
git clone <this-repo>
cd discord-voice-bot
pip install -r requirements.txt
```

### 2. Install FFmpeg

```bash
# Windows (winget)
winget install ffmpeg

# Or download from https://ffmpeg.org/download.html and add to PATH
```

### 3. Set up llama.cpp server

Download a GGUF model — recommended for your hardware (5–6GB RAM):

- [`dolphin-llama3-8B-Q4_K_M.gguf`](https://huggingface.co/bartowski/dolphin-llama3-8B-GGUF)
- [`Hermes-3-Llama-3.1-8B-Q4_K_M.gguf`](https://huggingface.co/bartowski/Hermes-3-Llama-3.1-8B-GGUF)

Start the server:

```bash
llama-server \
  -m path/to/your_model.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -ngl 20 \
  -c 4096 \
  --chat-template chatml
```

> **`-ngl 20`** — offloads 20 layers to your GPU. Adjust this number up/down based on how much VRAM you want to use. Start at 20, go higher if your GPU has headroom.

### 4. Set up Kokoro TTS (recommended)

```bash
pip install kokoro-onnx soundfile
```

Download the model files from the [kokoro-onnx releases](https://github.com/thewh1teagle/kokoro-onnx/releases):
- `kokoro-v1.0.onnx`
- `voices-v1.0.bin`

Place them in your project root (or update the path in `pipeline/tts.py`).

**Available voices:** `af_heart`, `af_bella`, `am_adam`, `am_michael`, `bf_emma`, `bm_george`

### 5. Set up Whisper STT

```bash
pip install pywhispercpp
```

On first run it will auto-download the model you specify. `small` is recommended:
- `tiny` — fastest, least accurate (~75MB)
- `small` — good balance (~466MB)
- `medium` — more accurate, slower (~1.5GB)

### 6. Configure

```bash
cp .env.example .env
```

Edit `.env`:
```env
DISCORD_TOKEN=your_discord_bot_token_here
WHISPER_MODEL=small
TTS_ENGINE=kokoro
KOKORO_VOICE=af_heart
```

### 7. Create your Discord bot

1. Go to [discord.com/developers](https://discord.com/developers/applications)
2. New Application → Bot
3. Enable **Message Content Intent** and **Server Members Intent**
4. Copy the token into `.env`
5. Invite the bot with scopes: `bot` + permissions: `Send Messages`, `Connect`, `Speak`, `Use Voice Activity`

---

## Running

```bash
# Terminal 1 — start LLM server first
llama-server -m your_model.gguf --port 8080 -ngl 20 -c 4096

# Terminal 2 — start bot
python bot.py
```

---

## Commands

| Command | Description |
|---------|-------------|
| `!join` / `!j` | Join your voice channel and start listening |
| `!leave` / `!l` / `!bye` | Leave the voice channel |
| `!reset` / `!r` | Clear conversation history |

---

## Tuning for your hardware

### GPU layer offloading (`-ngl`)

With 4GB VRAM and an 8B Q4 model, you can typically offload 20–28 layers to GPU. The rest runs on CPU/RAM. Experiment:

```bash
# Start conservative
llama-server -m model.gguf -ngl 15

# Watch VRAM usage with nvidia-smi, increase until it fills up
llama-server -m model.gguf -ngl 28
```

### Silence detection

If the bot triggers on background noise, raise `SILENCE_THRESHOLD` (default 500):
```env
SILENCE_THRESHOLD=800
```

If it's cutting you off mid-sentence, raise `SILENCE_DURATION`:
```env
SILENCE_DURATION=2.0
```

### Whisper model size

| Model | RAM | Speed | Accuracy |
|-------|-----|-------|----------|
| tiny | ~200MB | Very fast | OK |
| small | ~500MB | Fast | Good |
| medium | ~1.5GB | Medium | Great |

Given 32GB RAM, `small` or `medium` are both fine since they run on CPU.

---

## Architecture

```
discord.py VoiceClient
    └── VoiceSink (pipeline/sink.py)
            Buffers Opus audio per-user
            Converts 48kHz stereo → 16kHz mono PCM
            VAD: detects silence → queues utterance
                    ↓
            pipeline/stt.py (Whisper)
                    ↓
            pipeline/llm.py (llama.cpp server)
                    ↓
            pipeline/tts.py (Kokoro / Piper)
                    ↓
            discord.FFmpegPCMAudio → VoiceClient.play()
```

---

## Troubleshooting

**Bot joins but doesn't respond**
- Check that `llama-server` is running: `curl http://127.0.0.1:8080/health`
- Check `SILENCE_THRESHOLD` — may be too high if your mic is quiet

**`audioop` not found (Python 3.13+)**
- `audioop` was removed in Python 3.13. Use Python 3.11 or 3.12, or install `audioop-lts`:
  ```bash
  pip install audioop-lts
  ```

**Kokoro model files not found**
- Make sure `kokoro-v1.0.onnx` and `voices-v1.0.bin` are in the same directory as `bot.py`

**Very slow responses**
- Reduce `LLM_MAX_TOKENS` to 256
- Use `tiny` Whisper model
- Lower `-ngl` layers if VRAM is bottlenecking
