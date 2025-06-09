import discord
from enum import Enum
import os
import re
import json
import subprocess
from dotenv import load_dotenv
from faster_whisper import WhisperModel
import openai
from datetime import datetime
from io import BytesIO
from supabase import create_client, Client
from typing import Dict, List, Optional
import tempfile

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Bot(intents=intents)

model_size = "pariya47/distill-whisper-th-large-v3-ct2"
model = WhisperModel(model_size, device="cuda", compute_type="float16")

# Get environment variables
TOKEN = os.getenv("DISCORD_TOKEN")
raw_folder = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
openai.api_key  = os.getenv("OPENAI_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

connections = {}

class Sinks(Enum):
    mp3 = discord.sinks.MP3Sink()

def ffmpeg_mix_audio_streams(audio_streams: List[bytes], output_format: str = "mp3") -> bytes:
    if not audio_streams:
        return b""
    
    if len(audio_streams) == 1:
        # If only one stream, convert to desired format
        return ffmpeg_convert_audio(audio_streams[0], output_format)
    
    # Create temporary input files for FFmpeg
    temp_files = []
    try:
        # Write each audio stream to a temporary file
        for i, audio_data in enumerate(audio_streams):
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            temp_file.write(audio_data)
            temp_file.close()
            temp_files.append(temp_file.name)
        
        # Build FFmpeg command for mixing
        cmd = ["ffmpeg"]
        
        # Add input files
        for temp_file in temp_files:
            cmd.extend(["-i", temp_file])
        
        # Add filter complex for mixing
        filter_complex = f"amix=inputs={len(temp_files)}:duration=longest:dropout_transition=0"
        cmd.extend([
            "-filter_complex", filter_complex,
            "-c:a", "libmp3lame" if output_format == "mp3" else "pcm_s16le",
            "-f", output_format,
            "-"  # Output to stdout
        ])
        
        # Execute FFmpeg
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        
        return result.stdout
        
    except subprocess.CalledProcessError as e:
        raise Exception(f"FFmpeg mixing error: {e.stderr.decode()}")
    
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass

def ffmpeg_convert_audio(audio_data: bytes, output_format: str = "mp3", **kwargs) -> bytes:
    # Create temporary input file
    with tempfile.NamedTemporaryFile() as temp_input:
        temp_input.write(audio_data)
        temp_input.flush()
        
        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-i", temp_input.name,
            "-f", output_format
        ]
        
        # Add additional arguments
        for key, value in kwargs.items():
            cmd.extend([f"-{key}", str(value)])
        
        cmd.append("-")  # Output to stdout
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg conversion error: {e.stderr.decode()}")

async def transcribe_audio_from_memory(audio_data: bytes, model: WhisperModel) -> str:
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
        temp_file.write(audio_data)
        temp_file.flush()
        
        try:
            segments, _ = model.transcribe(temp_file.name, beam_size=5)
            transcription = "\n".join([segment.text for segment in segments])
            
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": 
                        """
                        คุณคือผู้ช่วยประชุม (meeting‐assistant) มีหน้าที่อ่านบันทึกการประชุมทั้งหมด แล้วสร้าง:
                        รายการหัวข้ออภิปรายหลัก (bullet points)
                        รายการงานที่ได้รับมอบหมายในรูปแบบ “ผู้รับมอบหมาย → งาน → กำหนดเวลา (ถ้ามี)”
                        สรุปเป้าหมาย การตัดสินใจ หรือขั้นตอนถัดไป
                        ให้ผลลัพธ์ออกมาใน 3 ส่วน ชื่อว่า:
                        • “หัวข้ออภิปราย”
                        • “งานที่ได้รับมอบหมาย”
                        • “เป้าหมายและการตัดสินใจ”
                        แต่ละบูลเล็ตรายการไม่เกินหนึ่งประโยค และใช้ข้อมูลจาก MongoDB memory ให้ครบถ้วน
                        """
                    },
                    {"role": "user", "content": f"Please summarize the following transcription:\n{transcription}"}
                ],
                temperature=0.3
            )
            return response
        finally:
            os.unlink(temp_file.name)
            
async def upload_audio(audio_bytes: bytes, storage_path: str, channel: discord.VoiceClient, content_type: str = "audio/mp3") -> bool:
    try:
        file_like = BytesIO(audio_bytes)
        result = supabase.storage.from_('meeting').upload(
            storage_path,
            file_like.read(),
            {"content-type": content_type}
        )
    except Exception as e:
        await channel.send(f"⚠️ Failed to upload audio file: {e}")

async def upload_metadata(data: dict, meeting_name: str, channel: discord.VoiceClient):
    try:
        # แปลง dict → JSON string → bytes
        json_data = json.dumps(data).encode('utf-8')
        files_like = BytesIO(json_data)
        
        storage_path = f'{meeting_name}/{meeting_name}_metadata.json'
        result = supabase.storage.from_("meeting").upload(
            storage_path,
            files_like.read(),
        )
    except Exception as e:
        await channel.send(f"⚠️ Failed to upload metadata: {e}")
        
# Callback when recording is finished          
async def finished_callback(sink, channel: discord.TextChannel, start_time: datetime):
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    meeting_name = datetime.now().strftime("meeting_%Y%m%d_%H%M%S")
    
    # Disconnect the voice client
    await sink.vc.disconnect()
    
    recorded_users = [f"<@{user_id}>" for user_id in sink.audio_data.keys()]
    await channel.send(
        f"🎙️Finished! Recorded audio for {', '.join(recorded_users)}."
        f" Duration: {duration:.2f} seconds."
    )
    
    try:
        audio_streams = []
        # Save individual recordings  
        for user_id, audio in sink.audio_data.items():
            audio.file.seek(0)  # ย้อนกลับไปต้นไฟล์
            audio_bytes = audio.file.read()
            audio_streams.append(audio_bytes)
            storage_path = f'{meeting_name}/individuals/{user_id}.mp3'
            await upload_audio(audio_bytes, storage_path, channel)
        
        mixed_audio = ffmpeg_mix_audio_streams(audio_streams, "mp3")
        
        mix_storage_path = f'{meeting_name}/meeting_mix.mp3'
        await upload_audio(mixed_audio, mix_storage_path, channel)

        # Transcribe the mixed audio
        transcription = await transcribe_audio_from_memory(mixed_audio, model)
        await channel.send(f"Transcription:\n{transcription}")
        
        # Upload transcription as text file
        transcription_bytes = transcription.encode('utf-8')
        transcription_path = f'{meeting_name}/transcription.txt'
        await upload_audio(transcription_bytes, transcription_path, channel)
        
        # Create and upload metadata JSON
        meeting_metadata = {
            "meeting_name": meeting_name,
            "channel_id": str(channel.id),
            "channel_name": channel.name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration": duration,
            "num_users": len(recorded_users),
            "recorded_users": recorded_users,
            "transcription_length": len(transcription),
        }
        
        await upload_metadata(
            data=meeting_metadata,
            maeting_name=meeting_name,
            channel=channel,
        )
        
        await channel.send(
            f"✅ Processing complete!\n"
            f"📝 Transcription: {len(transcription)} characters\n"
            f"```\n{transcription[:500]}{'...' if len(transcription) > 500 else ''}\n```"
        )
        
    except Exception as e:
        await channel.send(f"⚠️ An error occurred during processing: {e}")
        raise e

# Bot error handler
@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f"Command error: `{error}`")
    raise error
   
@bot.slash_command(name="start", description="เริ่มการอัดเสียงในห้องแชทเสียง")
async def start(ctx: discord.ApplicationContext):
    voice = ctx.author.voice

    if not voice:
        return await ctx.respond("You're not in a vc right now")

    try:
        sink_enum = Sinks.mp3  # Default to mp3 if no sink provided
    except KeyError:
        # available = ', '.join([s.name for s in Sinks])
        return await ctx.respond(f"Something went wrong")

    print(f'CHANNEL: {voice.channel.name} | SINK: {sink_enum.name}')
    vc = await voice.channel.connect()
    start_time = datetime.now()
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

    await ctx.respond("The recording has started!")

@bot.slash_command(name="stop", description="หยุดการอัดเสียงและอัปโหลดไปยัง MongoDB")
async def stop(ctx: discord.ApplicationContext):
    """Stop recording."""
    if ctx.guild.id in connections:
        session = connections[ctx.guild.id]
        vc = session['vc']
        start_time = session['start_time']
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        if vc.is_connected():
            vc.stop_recording()
            
        del connections[ctx.guild.id]
        
        await ctx.respond(f"⏱️ Meeting duration: {duration}")
    else:
        await ctx.respond("Not recording in this guild.")

bot.run(TOKEN)