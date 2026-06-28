"""
Chat Cog — plain text-to-text chat via slash command.

/listen designates ONE channel per server. Any non-command message posted
there gets sent to the LLM, and the bot replies with plain text — no STT,
no TTS, no voice channel involved. Separate from the voice pipeline's
conversation history (VoiceCog), so voice and text chats don't bleed
into each other.
"""

import asyncio
import discord
from discord.ext import commands

from pipeline.llm import get_llm_response
from config import Config


class ChatCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> channel_id the bot is currently listening to for text chat
        self.listen_channels: dict[int, int] = {}
        # guild_id -> conversation history for text chat
        self.histories: dict[int, list[dict]] = {}

    @discord.slash_command(
        name="listen",
        description="Make the bot listen for text chat in one channel (defaults to the current channel)",
    )
    async def listen(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.Option(
            discord.TextChannel,
            description="Channel to listen in (leave blank to use this channel)",
            required=False,
        ) = None,
    ):
        target = channel or ctx.channel
        self.listen_channels[ctx.guild.id] = target.id
        self.histories[ctx.guild.id] = []  # fresh history whenever the target changes
        await ctx.respond(
            f"👂 Listening for chat in {target.mention}. "
            f"Messages in other channels won't get a response."
        )

    @discord.slash_command(name="unlisten", description="Stop text-chat listening in this server")
    async def unlisten(self, ctx: discord.ApplicationContext):
        if self.listen_channels.pop(ctx.guild.id, None) is not None:
            self.histories.pop(ctx.guild.id, None)
            await ctx.respond("🔇 Stopped listening for text chat.")
        else:
            await ctx.respond("❌ I wasn't listening anywhere in this server.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots (including ourselves) and DMs
        if message.author.bot or not message.guild:
            return

        # Don't swallow ! commands — let them fall through to normal processing
        if message.content.startswith(Config.PREFIX):
            return

        guild_id = message.guild.id
        target_channel_id = self.listen_channels.get(guild_id)
        if target_channel_id is None or message.channel.id != target_channel_id:
            return

        if not message.content.strip():
            return  # e.g. attachment-only messages with no text

        history = self.histories.setdefault(guild_id, [])
        history.append({"role": "user", "content": message.content})

        async with message.channel.typing():
            response = await asyncio.get_event_loop().run_in_executor(
                None, get_llm_response, history
            )

        if not response:
            return

        history.append({"role": "assistant", "content": response})
        await message.channel.send(response)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChatCog(bot))
