"""
Voice Cog — handles join/leave commands and orchestrates the STT→LLM→TTS pipeline
"""

import asyncio
import discord
from discord.ext import commands

from pipeline.stt import transcribe_audio
from pipeline.llm import get_llm_response
from pipeline.tts import synthesize_speech
from pipeline.sink  import VoiceSink
from config import Config


class VoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> conversation history
        self.histories: dict[int, list[dict]] = {}

    # ── Commands ───────────────────────────────────────────────────────────────

    @commands.command(name="join", aliases=["j"])
    async def join(self, ctx: commands.Context):
        """Join the caller's voice channel and start listening."""
        if not ctx.author.voice:
            return await ctx.send("❌ You need to be in a voice channel first.")

        channel = ctx.author.voice.channel

        # Move if already in a different channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()

        self.histories[ctx.guild.id] = []
        await ctx.send(f"✅ Joined **{channel.name}** — listening!")
        self._start_listening(ctx)

    @commands.command(name="leave", aliases=["l", "bye"])
    async def leave(self, ctx: commands.Context):
        """Leave the voice channel."""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.histories.pop(ctx.guild.id, None)
            await ctx.send("👋 Left the voice channel.")
        else:
            await ctx.send("❌ I'm not in a voice channel.")

    @commands.command(name="reset", aliases=["r"])
    async def reset(self, ctx: commands.Context):
        """Clear the conversation history."""
        self.histories[ctx.guild.id] = []
        await ctx.send("🔄 Conversation history cleared.")

    # ── Listening loop ─────────────────────────────────────────────────────────

    def _start_listening(self, ctx: commands.Context):
        """Attach our custom sink and start the listen→process loop."""
        vc = ctx.voice_client
        sink = VoiceSink()

        def after_recording(exc):
            if exc:
                print(f"[Sink error] {exc}")

        vc.start_recording(sink, after_recording)

        # Kick off the background processing loop
        asyncio.create_task(self._process_loop(ctx, vc, sink))

    async def _process_loop(
        self,
        ctx: commands.Context,
        vc: discord.VoiceClient,
        sink: "VoiceSink",
    ):
        """
        Continuously polls the sink for completed audio chunks,
        runs them through STT→LLM→TTS, and plays the result back.
        """
        print(f"[Voice] Processing loop started for guild {ctx.guild.id}")

        while vc.is_connected():
            # Wait until the sink signals a complete utterance
            audio_bytes = await sink.get_utterance()

            if audio_bytes is None:
                await asyncio.sleep(0.1)
                continue

            # Don't interrupt ourselves
            if vc.is_playing():
                await asyncio.sleep(0.2)
                continue

            # --- STT ---
            await ctx.send("🎙️ *Transcribing...*", delete_after=5)
            transcript = await asyncio.get_event_loop().run_in_executor(
                None, transcribe_audio, audio_bytes
            )

            if not transcript or len(transcript.strip()) < 2:
                continue

            await ctx.send(f"📝 **You:** {transcript}")

            # --- LLM ---
            history = self.histories.setdefault(ctx.guild.id, [])
            history.append({"role": "user", "content": transcript})

            await ctx.send("🧠 *Thinking...*", delete_after=5)
            response = await asyncio.get_event_loop().run_in_executor(
                None, get_llm_response, history
            )

            if not response:
                continue

            history.append({"role": "assistant", "content": response})
            await ctx.send(f"🤖 **Bot:** {response}")

            # --- TTS ---
            await ctx.send("🔊 *Speaking...*", delete_after=3)
            audio_file = await asyncio.get_event_loop().run_in_executor(
                None, synthesize_speech, response
            )

            if audio_file and vc.is_connected():
                source = discord.FFmpegPCMAudio(audio_file)
                vc.play(source)

        print(f"[Voice] Processing loop ended for guild {ctx.guild.id}")


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceCog(bot))
