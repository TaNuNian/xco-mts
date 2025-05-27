import discord
from discord.ext import commands
from enum import Enum
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=">", intents=intents)

connections = {}

TOKEN = os.getenv("DISCORD_TOKEN")
FFMPEG_PATH = "./ffmpeg.exe" 

class Sinks(Enum):
    mp3 = discord.sinks.MP3Sink()
    wav = discord.sinks.WaveSink()
    pcm = discord.sinks.PCMSink()
    ogg = discord.sinks.OGGSink()
    mka = discord.sinks.MKASink()
    mkv = discord.sinks.MKVSink()
    mp4 = discord.sinks.MP4Sink()
    m4a = discord.sinks.M4ASink()


async def finished_callback(sink, channel: discord.TextChannel, *args):
    recorded_users = [f"<@{user_id}>" for user_id, audio in sink.audio_data.items()]
    await sink.vc.disconnect()
    files = [
        discord.File(audio.file, f"{user_id}.{sink.encoding}") for user_id, audio in sink.audio_data.items()
    ]
    await channel.send(
        f"Finished! Recorded audio for {', '.join(recorded_users)}.", files=files
    )
    
    os.makedirs("audio/sounds", exist_ok=True)
    files_name = []
    
    for user_id, audio in sink.audio_data.items():
        audio.file.seek(0)  # ย้อนกลับไปต้นไฟล์
        file_path = os.path.join("audio", "sounds", f"{user_id}.mp3")
        files_name.append(file_path)
        with open(f"audio/sounds/{user_id}.mp3", 'wb') as f:
            f.write(audio.file.read())
           
    ffmpeg_command = [FFMPEG_PATH]
    for file in files_name:
        ffmpeg_command += ["-i", file]
        
    filter_complex = f"amix=inputs={len(files_name)}:duration=longest:dropout_transition=0"
    output_path = os.path.join("audio", "meeting_mix.wav")
    ffmpeg_command += ["-filter_complex", filter_complex, output_path]
    
    subprocess.run(ffmpeg_command)
    
    with open(output_path, 'rb') as f:
        await channel.send(
            "Here is the mixed audio of all participants:", 
            file=discord.File(f, "meeting_mix.wav"))
    
@bot.command()
async def start(ctx: commands.Context, sink: str = "mp3"):
    """Record your voice!"""
    voice = ctx.author.voice

    if not voice:
        return await ctx.send("You're not in a vc right now")

    # Normalize and convert string to enum
    try:
        sink_enum = Sinks[sink.lower()]
    except KeyError:
        available = ', '.join([s.name for s in Sinks])
        return await ctx.send(f"Invalid sink. Choose one of: {available}")

    vc = await voice.channel.connect()
    connections.update({ctx.guild.id: vc})

    vc.start_recording(
        sink_enum.value,
        finished_callback,
        ctx.channel,
        sync_start=True
    )

    await ctx.send("The recording has started!")


@bot.command()
async def stop(ctx: commands.Context):
    """Stop recording."""
    if ctx.guild.id in connections:
        vc = connections[ctx.guild.id]
        vc.stop_recording()
        del connections[ctx.guild.id]
        await ctx.message.delete()
    else:
        await ctx.send("Not recording in this guild.")

bot.run(TOKEN)