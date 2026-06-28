"""
Voice Cog — STT -> LLM -> TTS pipeline using py-cord 2.7+ recording API.

In py-cord 2.7+:
- callback takes exactly one param: exception
- No custom args passed to callback anymore
- We keep a reference to the sink ourselves and read audio_data after stop
"""

import asyncio
import discord
from discord.ext import commands

from pipeline.stt import transcribe_audio
from pipeline.llm import get_llm_response
from pipeline.tts import synthesize_speech
from config import Config


class VoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.histories: dict[int, list[dict]] = {}
        self.connections: dict[int, discord.VoiceClient] = {}
        self.listening: dict[int, bool] = {}
        # Store sink reference per guild so callback can access it
        self.active_sinks: dict[int, discord.sinks.WaveSink] = {}
        self.done_events: dict[int, asyncio.Event] = {}

    @commands.command(name="join", aliases=["j"])
    async def join(self, ctx: commands.Context):
        if not ctx.author.voice:
            return await ctx.send("❌ You need to be in a voice channel first.")

        channel = ctx.author.voice.channel

        if ctx.voice_client:
            vc = ctx.voice_client
            await vc.move_to(channel)
        else:
            vc = await channel.connect()

        guild_id = ctx.guild.id
        self.connections[guild_id] = vc
        self.histories[guild_id] = []
        self.listening[guild_id] = True

        await ctx.send(f"✅ Joined **{channel.name}** — listening!")
        asyncio.create_task(self._listen_loop(ctx, vc))

    @commands.command(name="leave", aliases=["l", "bye"])
    async def leave(self, ctx: commands.Context):
        guild_id = ctx.guild.id
        self.listening[guild_id] = False

        vc = self.connections.get(guild_id) or ctx.voice_client
        if vc:
            if vc.is_recording():
                vc.stop_recording()
            await vc.disconnect(force=True)
            self.connections.pop(guild_id, None)
            self.histories.pop(guild_id, None)
            self.active_sinks.pop(guild_id, None)
            self.done_events.pop(guild_id, None)
            await ctx.send("👋 Left the voice channel.")
        else:
            await ctx.send("❌ I'm not in a voice channel.")

    @commands.command(name="reset", aliases=["r"])
    async def reset(self, ctx: commands.Context):
        self.histories[ctx.guild.id] = []
        await ctx.send("🔄 Conversation history cleared.")

    async def _listen_loop(self, ctx: commands.Context, vc: discord.VoiceClient):
        guild_id = ctx.guild.id
        CHUNK_SECONDS = 5

        print(f"[Voice] Listen loop started for guild {guild_id}")

        while self.listening.get(guild_id) and vc.is_connected():
            # Don't record while playing TTS
            if vc.is_playing():
                await asyncio.sleep(0.5)
                continue

            # Create a fresh sink and event for this chunk
            sink = discord.sinks.WaveSink()
            self.active_sinks[guild_id] = sink
            done_event = asyncio.Event()
            self.done_events[guild_id] = done_event

            # py-cord 2.7+: callback takes only (exception,)
            def make_callback(event: asyncio.Event):
                def callback(exc):
                    if exc:
                        print(f"[Voice] Recording error: {exc}")
                    try:
                        loop = asyncio.get_event_loop()
                        loop.call_soon_threadsafe(event.set)
                    except Exception as e:
                        print(f"[Voice] Event set error: {e}")
                return callback

            try:
                vc.start_recording(sink, make_callback(done_event))
            except Exception as e:
                print(f"[Voice] start_recording error: {e}")
                await asyncio.sleep(1)
                continue

            # Record for CHUNK_SECONDS
            await asyncio.sleep(CHUNK_SECONDS)

            # Stop recording
            if vc.is_recording():
                vc.stop_recording()

            # Wait for callback to confirm it's done
            try:
                await asyncio.wait_for(done_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                print("[Voice] Recording callback timed out, continuing anyway")

            # Read audio data from sink we stored
            audio_data = sink.audio_data
            if not audio_data:
                continue

            # Process each speaker's audio
            for user_id, audio in audio_data.items():
                member = ctx.guild.get_member(user_id)
                if member and member.bot:
                    continue

                audio.file.seek(0)
                wav_bytes = audio.file.read()
                if len(wav_bytes) < 5000:
                    continue

                # STT
                transcript = await asyncio.get_event_loop().run_in_executor(
                    None, transcribe_audio, wav_bytes
                )
                if not transcript or len(transcript.strip()) < 2:
                    continue

                name = member.display_name if member else str(user_id)
                await ctx.send(f"📝 **{name}:** {transcript}")

                # LLM
                history = self.histories.setdefault(guild_id, [])
                history.append({"role": "user", "content": transcript})

                await ctx.send("🧠 *Thinking...*", delete_after=5)
                response = await asyncio.get_event_loop().run_in_executor(
                    None, get_llm_response, history
                )
                if not response:
                    continue

                history.append({"role": "assistant", "content": response})
                await ctx.send(f"🤖 **Bot:** {response}")

                # Auto-save history to JSON
                try:
                    import json
                    with open("history.json", "w", encoding="utf-8") as f:
                        json.dump(self.histories, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"[History] Save error: {e}")

                # TTS
                audio_file = await asyncio.get_event_loop().run_in_executor(
                    None, synthesize_speech, response
                )
                if audio_file and vc.is_connected():
                    source = discord.FFmpegPCMAudio(audio_file)
                    vc.play(source)
                    while vc.is_playing():
                        await asyncio.sleep(0.2)

                break  # one speaker per chunk

        print(f"[Voice] Listen loop ended for guild {guild_id}")


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceCog(bot))