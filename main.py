"""
Main entry point for the Discord Meeting Transcription Bot.

This bot records voice channel conversations, transcribes them using Whisper,
generates meeting summaries using OpenAI, and stores everything in Supabase.
"""

import discord
from config import DISCORD_TOKEN
from bot_commands import setup_bot_commands


def main():
    """Initialize and run the Discord bot."""
    # Set up Discord bot with required intents
    intents = discord.Intents.default()
    intents.message_content = True
    bot = discord.Bot(intents=intents)
    
    # Set up bot commands
    setup_bot_commands(bot)
    
    # Add ready event
    @bot.event
    async def on_ready():
        print(f"{bot.user} has connected to Discord!")
        print(f"Bot is in {len(bot.guilds)} guilds")
    
    # Run the bot
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is not set")
    
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
