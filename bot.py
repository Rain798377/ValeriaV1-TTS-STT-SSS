from dotenv import load_dotenv
import os
load_dotenv(dotenv_path=r"D:\ValeriaV1-TTS-STT-SSS\.env", override=True)

import discord
from discord.ext import commands
from config import Config

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=Config.PREFIX, intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")
    print(f"🎙️  STT: {Config.WHISPER_MODEL}")
    print(f"🧠  LLM: {Config.LLAMA_API_URL}")
    print(f"🔊  TTS: {Config.TTS_ENGINE}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.send(f"❌ Error: {error}")

# Load cogs synchronously for py-cord
from cogs.voice import VoiceCog
from cogs.chat import ChatCog
bot.add_cog(VoiceCog(bot))
bot.add_cog(ChatCog(bot))

bot.run(Config.DISCORD_TOKEN)