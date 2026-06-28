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

Download a GGUF model — recommended for your hardware (~2GB):

- [`Dolphin3.0-Llama3.2-3B-Q4_K_M.gguf`](https://huggingface.co/bartowski/Dolphin3.0-Llama3.2-3B-GGUF)

Start the server:

```bash
llama-server \
  -m path/to/Dolphin3.0-Llama3.2-3B-Q4_K_M.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -ngl 99 \
  -c 4096 \
  --chat-template chatml
```

> **`-ngl 99`** — at this size (~2GB), the whole model fits comfortably on a 4GB GPU, so just offload everything (any number ≥ the model's actual layer count works; llama.cpp clamps it). No need to tune this down unless you're running something else on the GPU at the same time.

> **Note:** Dolphin models respond best when they know they're uncensored. If you want it to drop refusals entirely, set `SYSTEM_PROMPT` in your `.env` to explicitly state it's an unrestricted assistant — just telling it to "be helpful" isn't enough, Dolphin won't associate that with permissiveness on its own.

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
5. Invite the bot with scopes: `bot` + `applications.commands`, and permissions: `Send Messages`, `Connect`, `Speak`, `Use Voice Activity`

> **`applications.commands` scope is required** for `/listen` and `/unlisten` to show up — if you already invited the bot without it, re-invite using the same client ID with the scope added; it'll just update permissions on the existing install, no need to kick it first.
>
> Slash commands sync globally on startup by default, which can take up to an hour to propagate the first time. If you want to test instantly while developing, you can scope a command to your server only by passing `guild_ids=[YOUR_GUILD_ID]` to the `@discord.slash_command(...)` decorator in `cogs/chat.py`.

---

## Running

```bash
# Terminal 1 — start LLM server first
llama-server -m Dolphin3.0-Llama3.2-3B-Q4_K_M.gguf --port 8080 -ngl 99 -c 4096

# Terminal 2 — start bot
python bot.py
```

---

## Commands

| Command | Description |
|---------|-------------|
| `!join` / `!j` | Join your voice channel and start listening |
| `!leave` / `!l` / `!bye` | Leave the voice channel |
| `!reset` / `!r` | Clear voice conversation history |
| `/listen [channel]` | Start text-to-text chat in one channel (defaults to the channel you run it in) — no voice involved, just plain messages in → LLM reply out |
| `/unlisten` | Stop text-to-text chat for this server |

Voice (`!` commands) and text (`/listen`) keep **separate** conversation histories — talking to it in voice doesn't carry context into the text channel, and vice versa.

---

## Tuning for your hardware

### GPU layer offloading (`-ngl`)

With 4GB VRAM and a 3B Q4 model (~2GB), the whole model fits on GPU — set `-ngl 99` and don't worry about it. This is different from an 8B model, where you'd have to partially offload layers and split the rest to CPU/RAM. If you ever swap to a bigger model later and start hitting VRAM limits, that's when you'd dial this down:

```bash
# Full offload (recommended for 3B at this VRAM size)
llama-server -m model.gguf -ngl 99

# If you upgrade to a bigger model and run out of VRAM, scale back
llama-server -m model.gguf -ngl 20
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
