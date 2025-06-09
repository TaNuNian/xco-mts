import discord
from enum import Enum
import os
import re
import json
import subprocess
from dotenv import load_dotenv
from faster_whisper import WhisperModel
from datetime import datetime
from io import BytesIO
import tempfile
import requests
from typing import Dict, List, Optional
from supabase import create_client, Client

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Bot(intents=intents)

model_size = "pariya47/distill-whisper-th-large-v3-ct2"
model = WhisperModel(model_size, device="cuda", compute_type="float16")

# Get environment variables
TOKEN = os.getenv("DISCORD_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://<project>.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "<your-service-role-key>")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
connections = {}

class Sinks(Enum):
    mp3 = discord.sinks.MP3Sink()

def ffmpeg_mix_audio_streams(audio_streams: List[bytes], output_format: str = "mp3") -> bytes:
    """
    Mix multiple audio streams in memory using FFmpeg.
    
    Args:
        audio_streams: List of audio data as bytes
        output_format: Output format (mp3, wav, etc.)
    
    Returns:
        Mixed audio as bytes
    """
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
    """
    Convert audio format using FFmpeg in memory.
    
    Args:
        audio_data: Input audio as bytes
        output_format: Output format
        **kwargs: Additional FFmpeg arguments
    
    Returns:
        Converted audio as bytes
    """
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

def ffmpeg_extract_audio_segment(audio_data: bytes, start_time: float, duration: float) -> bytes:
    """
    Extract a segment from audio using FFmpeg.
    
    Args:
        audio_data: Input audio as bytes
        start_time: Start time in seconds
        duration: Duration in seconds
    
    Returns:
        Audio segment as bytes
    """
    with tempfile.NamedTemporaryFile() as temp_input:
        temp_input.write(audio_data)
        temp_input.flush()
        
        cmd = [
            "ffmpeg",
            "-i", temp_input.name,
            "-ss", str(start_time),
            "-t", str(duration),
            "-f", "mp3",
            "-"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg segment extraction error: {e.stderr.decode()}")

async def upload_audio_to_supabase(audio_bytes: bytes, storage_path: str, content_type: str = "audio/mp3") -> bool:
    """
    Upload audio data to Supabase storage.
    
    Args:
        audio_bytes: Audio data as bytes
        storage_path: Path in storage bucket
        content_type: MIME type
    
    Returns:
        Success status
    """
    try:
        result = supabase.storage.from_('meeting').upload(
            storage_path,
            audio_bytes,
            {"content-type": content_type}
        )
        return True
    except Exception as e:
        print(f"Upload error: {e}")
        return False

async def upload_metadata_to_supabase(data: dict, meeting_name: str) -> bool:
    """
    Upload metadata JSON to Supabase storage.
    
    Args:
        data: Metadata dictionary
        meeting_name: Meeting identifier
    
    Returns:
        Success status
    """
    try:
        json_data = json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
        storage_path = f'{meeting_name}/{meeting_name}_metadata.json'
        
        result = supabase.storage.from_("meeting").upload(
            storage_path,
            json_data,
            {"content-type": "application/json"}
        )
        return True
    except Exception as e:
        print(f"Metadata upload error: {e}")
        return False

async def transcribe_audio_from_memory(audio_data: bytes, model: WhisperModel) -> str:
    """
    Transcribe audio directly from memory using a temporary file.
    
    Args:
        audio_data: Audio data as bytes
        model: Whisper model instance
    
    Returns:
        Transcribed text
    """
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
        temp_file.write(audio_data)
        temp_file.flush()
        
        try:
            segments, _ = model.transcribe(temp_file.name, beam_size=5)
            transcription = "\n".join([segment.text for segment in segments])
            return transcription
        finally:
            os.unlink(temp_file.name)

async def finished_callback(sink, channel: discord.TextChannel, start_time: datetime):
    """Enhanced callback with memory-based processing."""
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    meeting_name = datetime.now().strftime("meeting_%Y%m%d_%H%M%S")
    
    # Disconnect the voice client
    await sink.vc.disconnect()
    
    recorded_users = [f"<@{user_id}>" for user_id in sink.audio_data.keys()]
    await channel.send(
        f"🎙️ Finished! Recorded audio for {', '.join(recorded_users)}. "
        f"Duration: {duration:.2f} seconds. Processing..."
    )
    
    try:
        # Process individual recordings
        audio_streams = []
        individual_uploads = []
        
        for user_id, audio in sink.audio_data.items():
            audio.file.seek(0)
            audio_bytes = audio.file.read()
            audio_streams.append(audio_bytes)
            
            # Upload individual recording
            storage_path = f'{meeting_name}/individuals/{user_id}.mp3'
            upload_success = await upload_audio_to_supabase(audio_bytes, storage_path)
            individual_uploads.append(upload_success)
        
        # Mix audio streams in memory
        await channel.send("🔄 Mixing audio streams...")
        mixed_audio = ffmpeg_mix_audio_streams(audio_streams, "mp3")
        
        # Upload mixed audio
        mix_storage_path = f'{meeting_name}/meeting_mix.mp3'
        mix_upload_success = await upload_audio_to_supabase(mixed_audio, mix_storage_path)
        
        # Transcribe the mixed audio
        await channel.send("🎯 Transcribing audio...")
        transcription = await transcribe_audio_from_memory(mixed_audio, model)
        
        # Upload transcription as text file
        transcription_bytes = transcription.encode('utf-8')
        transcription_path = f'{meeting_name}/transcription.txt'
        await upload_audio_to_supabase(
            transcription_bytes, 
            transcription_path, 
            "text/plain"
        )
        
        # Create and upload metadata
        meeting_metadata = {
            "meeting_name": meeting_name,
            "channel_id": str(channel.id),
            "channel_name": channel.name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration": duration,
            "num_users": len(recorded_users),
            "recorded_users": recorded_users,
            "individual_uploads_success": all(individual_uploads),
            "mix_upload_success": mix_upload_success,
            "transcription_length": len(transcription),
            "processing_completed": True
        }
        
        metadata_success = await upload_metadata_to_supabase(meeting_metadata, meeting_name)
        
        # Send results
        success_count = sum(individual_uploads) + mix_upload_success + metadata_success
        total_uploads = len(individual_uploads) + 2  # mix + metadata
        
        await channel.send(
            f"✅ Processing complete!\n"
            f"📁 Uploads: {success_count}/{total_uploads} successful\n"
            f"📝 Transcription: {len(transcription)} characters\n"
            f"```\n{transcription[:500]}{'...' if len(transcription) > 500 else ''}\n```"
        )
        
    except Exception as e:
        await channel.send(f"❌ Processing error: {e}")
        print(f"Processing error: {e}")

# Enhanced audio processing commands
@bot.slash_command(name="process_audio", description="Process uploaded audio file with FFmpeg")
async def process_audio(
    ctx: discord.ApplicationContext, 
    audio_file: discord.Attachment,
    start_time: float = 0,
    duration: Optional[float] = None
):
    """Process an uploaded audio file with optional trimming."""
    if not audio_file.content_type.startswith('audio/'):
        return await ctx.respond("❌ Please upload an audio file.")
    
    await ctx.defer()
    
    try:
        # Download the audio file
        audio_data = await audio_file.read()
        
        # Process based on parameters
        if duration:
            # Extract segment
            processed_audio = ffmpeg_extract_audio_segment(audio_data, start_time, duration)
            filename = f"segment_{start_time}s_{duration}s.mp3"
        else:
            # Just convert format
            processed_audio = ffmpeg_convert_audio(audio_data, "mp3")
            filename = f"converted_{audio_file.filename}"
        
        # Create a file-like object for Discord
        processed_file = discord.File(
            BytesIO(processed_audio), 
            filename=filename
        )
        
        await ctx.followup.send(
            f"🎵 Processed audio file:", 
            file=processed_file
        )
        
    except Exception as e:
        await ctx.followup.send(f"❌ Processing failed: {e}")

@bot.slash_command(name="start", description="เริ่มการอัดเสียงในห้องแชทเสียง")
async def start(ctx: discord.ApplicationContext):
    voice = ctx.author.voice

    if not voice:
        return await ctx.respond("❌ You're not in a voice channel right now")

    if ctx.guild.id in connections:
        return await ctx.respond("❌ Already recording in this server")

    try:
        sink_enum = Sinks.mp3
    except KeyError:
        return await ctx.respond("❌ Something went wrong with audio sink")

    print(f'🎙️ CHANNEL: {voice.channel.name} | SINK: {sink_enum.name}')
    
    try:
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

        await ctx.respond("🔴 Recording started! Use `/stop` to finish.")
        
    except Exception as e:
        await ctx.respond(f"❌ Failed to start recording: {e}")

@bot.slash_command(name="stop", description="หยุดการอัดเสียงและอัปโหลดไปยัง Supabase")
async def stop(ctx: discord.ApplicationContext):
    """Stop recording and process audio."""
    if ctx.guild.id not in connections:
        return await ctx.respond("❌ Not recording in this server")
    
    session = connections[ctx.guild.id]
    vc = session['vc']
    start_time = session['start_time']
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    try:
        if vc.is_connected():
            vc.stop_recording()
        
        del connections[ctx.guild.id]
        
        await ctx.respond(
            f"⏹️ Recording stopped!\n"
            f"⏱️ Duration: {duration:.2f} seconds\n"
            f"🔄 Processing will begin shortly..."
        )
        
    except Exception as e:
        await ctx.respond(f"❌ Error stopping recording: {e}")

@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f"❌ Command error: `{error}`")
    raise error

@bot.event
async def on_ready():
    print(f"🤖 {bot.user} is ready!")
    print(f"📊 Connected to {len(bot.guilds)} servers")

bot.run(TOKEN)