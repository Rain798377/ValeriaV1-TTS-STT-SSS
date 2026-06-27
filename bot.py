"""
Discord Voice Bot - Main Entry Point
STT (Whisper) -> LLM (llama.cpp) -> TTS (Kokoro/Piper)
"""

import asyncio
import discord
from discord.ext import commands
from config import Config

# Setup intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=Config.PREFIX, intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")
    print(f"🎙️  STT: whisper.cpp ({Config.WHISPER_MODEL})")
    print(f"🧠  LLM: llama.cpp @ {Config.LLAMA_API_URL}")
    print(f"🔊  TTS: {Config.TTS_ENGINE}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.send(f"❌ Error: {error}")

async def main():
    await bot.load_extension("cogs.voice")
    await bot.start(Config.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
