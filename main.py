import discord
from discord.ext import commands
from enum import Enum
import os
import subprocess
from dotenv import load_dotenv
from pymongo import MongoClient
from gridfs import GridFS
import shutil

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=">", intents=intents)

connections = {}

TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
FFMPEG_PATH = "./ffmpeg.exe" 

client = MongoClient(MONGO_URI)
db = client["xco-mts"]
fs = GridFS(db)

class Sinks(Enum):
    mp3 = discord.sinks.MP3Sink()
    wav = discord.sinks.WaveSink()
    pcm = discord.sinks.PCMSink()
    ogg = discord.sinks.OGGSink()
    mka = discord.sinks.MKASink()
    mkv = discord.sinks.MKVSink()
    mp4 = discord.sinks.MP4Sink()
    m4a = discord.sinks.M4ASink()

def upload_file_to_mongo(root_folder_path, meeting_name):
    for root, dirs, files in os.walk(root_folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, root_folder_path)
            gridfs_filename = f'{meeting_name}/{relative_path.replace(os.sep, '/')}'

            if "sounds" in relative_path:
                user_id = os.path.splitext(file)[0]
                metadata={
                    "meeting": meeting_name,
                    "type": "individual",
                    "user": user_id
                }
            else:
                metadata = {
                    "meeting": meeting_name,
                    "type": "mixed"
                }
            with open(file_path, 'rb') as f:
                data = f.read()
                fs.put(
                    data, 
                    filename=gridfs_filename, 
                    metadata=metadata
                )
                
async def finished_callback(sink, channel: discord.TextChannel, *args):
    recorded_users = [f"<@{user_id}>" for user_id, audio in sink.audio_data.items()]
    await sink.vc.disconnect()
    files = [
        discord.File(audio.file, f"{user_id}.{sink.encoding}") for user_id, audio in sink.audio_data.items()
    ]
    
    await channel.send(
        f"Finished! Recorded audio for {', '.join(recorded_users)}."
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
    
    upload_file_to_mongo("audio", "meeting1")
    await channel.send(
        "Uploaded audio files to MongoDB successfully!",
    )
    # with open(output_path, 'rb') as f:
    #     await channel.send(
    #         "Here is the mixed audio of all participants:", 
    #         file=discord.File(f, "meeting_mix.wav"))
    try:
        shutil.rmtree("audio")
    except Exception as e:
        await channel.send(f"⚠️ Failed to delete local files: {e}")
    
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