"""Discord bot commands for meeting recording."""

import discord
from meeting_recorder import MeetingRecorder

# Initialize meeting recorder
recorder = MeetingRecorder()


def setup_bot_commands(bot: discord.Bot):
    """
    Set up Discord bot slash commands.
    
    Args:
        bot: Discord bot instance
    """
    
    @bot.slash_command(name="start", description="เริ่มการอัดเสียงในห้องแชทเสียง")
    async def start_recording(ctx: discord.ApplicationContext):
        """Start recording in the voice channel."""
        await recorder.start_recording(ctx)

    @bot.slash_command(name="stop", description="หยุดการอัดเสียงและอัพโหลดไปยัง Supabase")
    async def stop_recording(ctx: discord.ApplicationContext):
        """Stop recording and process the audio."""
        await recorder.stop_recording(ctx)

    @bot.event
    async def on_command_error(ctx, error):
        """Handle command errors."""
        await ctx.send(f"Command error: `{error}`")
        raise error
