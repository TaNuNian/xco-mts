import discord
from enum import Enum
import os
import subprocess
from dotenv import load_dotenv
from pymongo import MongoClient
from gridfs import GridFS
import shutil
from datetime import datetime

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Bot(intents=intents)

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

def upload_file_to_mongo(root_folder_path, meeting_name, start_time, end_tim, duration):
    for root, _, files in os.walk(root_folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, root_folder_path)
            gridfs_filename = f'{meeting_name}/{relative_path.replace(os.sep, '/')}'

            if "sounds" in relative_path:
                user_id = os.path.splitext(file)[0]
                metadata={
                    "meeting": meeting_name,
                    "type": "individual",
                    "user": user_id,
                    "start_time": start_time.isoformat(),
                    "end_time": end_tim.isoformat(),
                    "duration": duration
                }
            else:
                metadata = {
                    "meeting": meeting_name,
                    "type": "mixed",
                    "start_time": start_time.isoformat(),
                    "end_time": end_tim.isoformat(),
                    "duration": duration
                }
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()
                    fs.put(
                        data, 
                        filename=gridfs_filename, 
                        metadata=metadata
                    )
            except Exception as e:
                print(f"Error uploading {file_path} to MongoDB: {e}")
              
async def finished_callback(sink, channel: discord.TextChannel, start_time: datetime):
    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()
    
    recorded_users = [f"<@{user_id}>" for user_id in sink.audio_data.keys()]
    await sink.vc.disconnect()
    
    await channel.send(
        f"Finished! Recorded audio for {', '.join(recorded_users)}."
        f" Duration: {duration:.2f} seconds."
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
    
    meeting_name = f"meeting_{start_time.strftime('%Y%m%d_%H%M%S')}"

    upload_file_to_mongo("audio", meeting_name, start_time, end_time, duration)
    await channel.send(
        "Uploaded audio files to MongoDB successfully!",
    )
    
    try:
        shutil.rmtree("audio")
    except Exception as e:
        await channel.send(f"⚠️ Failed to delete local files: {e}")
    
@bot.slash_command(name="start", description="เริ่มการอัดเสียงในห้องแชทเสียง")
async def start(
        ctx: discord.ApplicationContext,
        sink: str = discord.Option(
            name="sink",
            description="Choose the audio format to record in.",
            choices=[s.name for s in Sinks],
            default="mp3"
        )
    ):
    voice = ctx.author.voice

    if not voice:
        return await ctx.send("You're not in a vc right now")

    try:
        sink_enum = Sinks[sink.lower()]
    except KeyError:
        available = ', '.join([s.name for s in Sinks])
        return await ctx.send(f"Invalid sink. Choose one of: {available}")

    vc = await voice.channel.connect()
    start_time = datetime.utcnow()
    connections[ctx.guild.id] = {
        "vc": vc,
        "start_time": start_time
    }
    
    vc.start_recording(
        sink_enum.value,
        finished_callback,
        ctx.channel,
        start_time,
        sync_start=True
    )

    await ctx.send("The recording has started!")

@bot.slash_command(name="stop", description="หยุดการอัดเสียงและอัปโหลดไปยัง MongoDB")
async def stop(ctx: discord.ApplicationContext):
    """Stop recording."""
    if ctx.guild.id in connections:
        session = connections[ctx.guild.id]
        vc = session['vc']
        start_time = session['start_time']
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        if vc.is_connected():
            vc.stop_recording()
            
        del connections[ctx.guild.id]
        
        await ctx.send(f"⏱️ Meeting duration: {duration}")
    else:
        await ctx.send("Not recording in this guild.")

bot.run(TOKEN)