"""Meeting recorder class to handle recording sessions."""

from datetime import datetime
from typing import Dict, List
import discord
from audio_processor import ffmpeg_mix_audio_streams
from transcription_service import transcribe_audio_from_memory, summarize_transcription
from storage_service import upload_audio, upload_metadata, upload_text_file, get_transcript
from config import whisper_model
from utils import generate_meeting_name, format_duration, format_user_mentions, truncate_text
import asyncio
from io import BytesIO

class MeetingRecorder:
    """Handles meeting recording and processing."""
    
    def __init__(self):
        self.connections: Dict[int, Dict] = {}
        self.background_tasks: Dict[int, asyncio.Task] = {}  # guild_id -> background loop
    
    async def _record_loop(self, guild_id: int, sink, channel: discord.TextChannel, start_time: datetime, meeting_name: str):
        """
        Loop to handle recording in a voice channel.
        
        Args:
            guild_id: ID of the guild
            sink: Discord audio sink
            channel: Discord text channel
            start_time: Recording start time
        """
        counter = 0
        while guild_id in self.connections:
            await asyncio.sleep(300)  # Save every 5 minutes
            
            audio_streams = []
            recorded_user_ids = list(sink.audio_data.keys())
            
            for user_id, audio in sink.audio_data.items():
                audio.file.seek(0)
                audio_bytes = audio.file.read()
                audio_streams.append(audio_bytes)
                
                storage_path = f'{meeting_name}/segments/{counter}/user_{user_id}.mp3'
                await upload_audio(audio_bytes, storage_path, channel)
                
                audio.file = BytesIO()  # Clear the memory buffer
            
            mixed = ffmpeg_mix_audio_streams(audio_streams, "mp3")
            storage_path = f'{meeting_name}/audio_segments/{counter}.mp3'
            await upload_audio(mixed, storage_path, channel)
            
            transcript = await transcribe_audio_from_memory(mixed, whisper_model)
            text = transcript
            
            await channel.send(f"📄 Transcript (Segment {counter}):\n```{truncate_text(text, 300)}```")
            
            await upload_text_file(
                text, f'{meeting_name}/text_segments/{counter}.txt', channel
            )
            
            counter += 1
                
    async def start_recording(self, ctx: discord.ApplicationContext) -> bool:
        """
        Start recording in a voice channel.
        
        Args:
            ctx: Discord application context
            
        Returns:
            True if recording started successfully, False otherwise
        """
        voice = ctx.author.voice

        if not voice:
            await ctx.respond("You're not in a voice channel right now")
            return False

        try:
            sink = discord.sinks.MP3Sink()
        except Exception:
            await ctx.respond("Something went wrong with audio sink setup")
            return False

        print(f'CHANNEL: {voice.channel.name} | SINK: MP3')
        
        try:
            vc = await voice.channel.connect()
            start_time = datetime.now()
            
            self.connections[ctx.guild.id] = {
                "vc": vc,
                "start_time": start_time
            }

            vc.start_recording(
                sink,
                self._finished_callback,
                ctx.channel,
                start_time,
                sync_start=True
            )
            
            task = asyncio.create_task(
                self._record_loop(ctx.guild.id, sink, ctx.channel, start_time, generate_meeting_name(start_time))
            )
            self.background_tasks[ctx.guild.id] = task

            await ctx.respond("🎙️ The recording has started!")
            return True
            
        except Exception as e:
            await ctx.respond(f"Failed to start recording: {e}")
            return False
    
    async def stop_recording(self, ctx: discord.ApplicationContext) -> bool:
        """
        Stop recording in the current guild.
        
        Args:
            ctx: Discord application context
            
        Returns:
            True if recording stopped successfully, False otherwise
        """
        if ctx.guild.id not in self.connections:
            await ctx.respond("Not recording in this guild.")
            return False

        session = self.connections[ctx.guild.id]
        vc = session['vc']
        start_time = session['start_time']
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        if vc.is_connected():
            vc.stop_recording()

        del self.connections[ctx.guild.id]
        
        if ctx.guild.id in self.background_tasks:
            self.background_tasks[ctx.guild.id].cancel()
            del self.background_tasks[ctx.guild.id]
            
        await ctx.respond(f"⏱️ Meeting stopped. Duration: {format_duration(duration)}")
        return True
    
    async def _finished_callback(self, sink, channel: discord.TextChannel, start_time: datetime):
        """
        Callback function executed when recording is finished.
        
        Args:
            sink: Discord audio sink
            channel: Discord text channel
            start_time: Recording start time
        """
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        meeting_name = generate_meeting_name(end_time)

        # Disconnect the voice client
        await sink.vc.disconnect()

        recorded_user_ids = list(sink.audio_data.keys())
        recorded_users = format_user_mentions([str(uid) for uid in recorded_user_ids])
        
        await channel.send(
            f"🎙️ Finished! Recorded audio for {recorded_users}. "
            f"Duration: {format_duration(duration)}."
        )

        try:
            await self._process_recording(sink, channel, start_time, end_time, meeting_name, recorded_user_ids)
        except Exception as e:
            await channel.send(f"⚠️ An error occurred during processing: {e}")
            raise e

    async def _process_recording(
        self, 
        sink, 
        channel: discord.TextChannel, 
        start_time: datetime, 
        end_time: datetime,
        meeting_name: str,
        recorded_user_ids: List[int]
    ):
        """
        Process the recorded audio: mix, transcribe, and upload.
        
        Args:
            sink: Discord audio sink
            channel: Discord text channel
            start_time: Recording start time
            end_time: Recording end time
            meeting_name: Generated meeting name
            recorded_user_ids: List of recorded user IDs
        """
        audio_streams = []
        
        # Save individual recordings and collect audio streams
        for user_id, audio in sink.audio_data.items():
            audio.file.seek(0)  # Reset file pointer
            audio_bytes = audio.file.read()
            audio_streams.append(audio_bytes)
            
            storage_path = f'{meeting_name}/individuals/{user_id}.mp3'
            await upload_audio(audio_bytes, storage_path, channel)

        # Mix all audio streams
        mixed_audio = ffmpeg_mix_audio_streams(audio_streams, "mp3")
        mix_storage_path = f'{meeting_name}/audio_segments/last_audio.mp3'
        await upload_audio(mixed_audio, mix_storage_path, channel)
        
        # Transcribe the mixed audio
        last_transcription = await transcribe_audio_from_memory(mixed_audio, whisper_model)
        
        # Get full transcript from Supabase storage
        texts = await get_transcript(meeting_name)
        full_transcript = texts + last_transcription
        
        # Upload the full transcript as a text file
        await upload_text_file(
            full_transcript, f'{meeting_name}/full_transcript.txt', channel
        )
        
        # Summarize the transcription
        transcription_content = await summarize_transcription(full_transcript)
        
        await channel.send(f"📝 Transcription:\n{transcription_content}")

        # Upload transcription as text file
        transcription_path = f'{meeting_name}/transcription.txt'
        await upload_text_file(transcription_content, transcription_path, channel)

        # Create and upload metadata
        duration = (end_time - start_time).total_seconds()
        recorded_user_mentions = format_user_mentions([str(uid) for uid in recorded_user_ids])
        
        meeting_metadata = {
            "meeting_name": meeting_name,
            "channel_id": str(channel.id),
            "channel_name": channel.name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration": duration,
            "duration_formatted": format_duration(duration),
            "num_users": len(recorded_user_ids),
            "recorded_users": recorded_user_mentions,
            "recorded_user_ids": [str(uid) for uid in recorded_user_ids],
            "transcription_length": len(transcription_content)
        }

        await upload_metadata(meeting_metadata, meeting_name, channel)

        # Send completion message with preview
        preview_text = truncate_text(transcription_content, 500)
            
        await channel.send(
            f"✅ Processing complete!\n"
            f"📝 Transcription: {len(transcription_content)} characters\n"
            f"⏱️ Duration: {format_duration(duration)}\n"
            f"```\n{preview_text}\n```"
        )
