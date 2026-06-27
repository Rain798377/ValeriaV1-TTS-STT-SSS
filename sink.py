"""
VoiceSink — captures Discord audio per-user with basic VAD
(Voice Activity Detection) so we know when someone finishes talking.

Discord sends 20ms Opus frames at 48kHz stereo.
We decode to PCM, detect silence, then queue completed utterances.
"""

import asyncio
import audioop
import io
import struct
import time
import wave

import discord
from discord.sinks import Sink

from config import Config


class VoiceSink(Sink):
    """
    A Discord audio sink that:
    1. Buffers PCM audio per user
    2. Detects silence using RMS energy
    3. Queues complete utterances for the processing loop
    """

    def __init__(self):
        super().__init__()
        # user_id -> list of PCM chunks
        self._buffers: dict[int, list[bytes]] = {}
        # user_id -> last active timestamp
        self._last_active: dict[int, float] = {}
        # Completed utterances ready to process
        self._utterance_queue: asyncio.Queue = asyncio.Queue()
        # Background VAD task
        self._vad_task: asyncio.Task | None = None

    def write(self, data: bytes, user: discord.Member):
        """Called by discord.py for every 20ms audio frame."""
        user_id = user.id

        # Decode Opus to PCM (discord.py handles this internally)
        # data here is already decoded PCM int16 stereo 48kHz
        rms = self._rms(data)

        if rms > Config.SILENCE_THRESHOLD:
            # Active speech — buffer it
            if user_id not in self._buffers:
                self._buffers[user_id] = []
            self._buffers[user_id].append(data)
            self._last_active[user_id] = time.monotonic()
        else:
            # Silence — check if we should finalize this user's utterance
            if user_id in self._last_active:
                elapsed = time.monotonic() - self._last_active[user_id]
                if elapsed >= Config.SILENCE_DURATION and user_id in self._buffers:
                    audio = self._finalize(user_id)
                    if audio:
                        # Schedule queue put on the event loop
                        try:
                            loop = asyncio.get_event_loop()
                            loop.call_soon_threadsafe(
                                self._utterance_queue.put_nowait, audio
                            )
                        except Exception as e:
                            print(f"[Sink] Queue error: {e}")

    async def get_utterance(self) -> bytes | None:
        """
        Returns the next completed audio utterance (WAV bytes),
        or None if nothing is ready yet (non-blocking).
        """
        try:
            return self._utterance_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def cleanup(self):
        """Called when the sink is stopped."""
        self._buffers.clear()
        self._last_active.clear()

    # ── Internals ──────────────────────────────────────────────────────────────

    def _finalize(self, user_id: int) -> bytes | None:
        """Convert buffered PCM chunks into a 16kHz mono WAV for Whisper."""
        chunks = self._buffers.pop(user_id, [])
        self._last_active.pop(user_id, None)

        if not chunks:
            return None

        # Combine all chunks
        raw_pcm = b"".join(chunks)

        # Discord gives us 48kHz stereo int16 PCM
        # Whisper wants 16kHz mono int16 PCM
        # Step 1: stereo -> mono (average L+R)
        mono = audioop.tomono(raw_pcm, 2, 0.5, 0.5)
        # Step 2: 48kHz -> 16kHz (downsample by 3)
        resampled, _ = audioop.ratecv(mono, 2, 1, 48000, 16000, None)

        # Wrap in WAV container
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)   # int16 = 2 bytes
            wf.setframerate(16000)
            wf.writeframes(resampled)

        return buf.getvalue()

    @staticmethod
    def _rms(pcm: bytes) -> float:
        """Calculate RMS energy of a PCM int16 chunk."""
        if len(pcm) < 2:
            return 0.0
        try:
            return audioop.rms(pcm, 2)
        except Exception:
            return 0.0
