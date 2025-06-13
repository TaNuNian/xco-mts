"""Meeting recorder class to handle recording sessions."""

from datetime import datetime
from typing import Dict, List
import discord
from audio_processor import ffmpeg_mix_audio_streams
from transcription_service import transcribe_audio_from_memory
from storage_service import upload_audio, upload_metadata, upload_text_file
from config import whisper_model
from utils import generate_meeting_name, format_duration, format_user_mentions, truncate_text


class MeetingRecorder:
    """Handles meeting recording and processing."""
    
    def __init__(self):
        self.connections: Dict[int, Dict] = {}
    
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
        mix_storage_path = f'{meeting_name}/meeting_mix.mp3'
        await upload_audio(mixed_audio, mix_storage_path, channel)

        # Transcribe the mixed audio
        transcription = await transcribe_audio_from_memory(mixed_audio, whisper_model)
        transcription_content = transcription.choices[0].message.content
        from structure_output import make_structure_output
        structured_output = await make_structure_output(transcription_content)
        await channel.send(f"📝 Transcription:\n{transcription_content}")
        await channel.send(structured_output.model_dump_json())

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
