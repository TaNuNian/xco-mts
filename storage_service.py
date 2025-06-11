"""Storage service for uploading files to Supabase."""

import json
from io import BytesIO
from typing import Dict, Union
import discord
from config import supabase_client


async def upload_audio(
    audio_bytes: bytes, 
    storage_path: str, 
    channel: Union[discord.TextChannel, discord.VoiceChannel], 
    content_type: str = "audio/mp3"
) -> bool:
    """
    Upload audio data to Supabase storage.
    
    Args:
        audio_bytes: Audio data as bytes
        storage_path: Storage path in Supabase
        channel: Discord channel for error messages
        content_type: MIME type of the content
        
    Returns:
        True if successful, False otherwise
    """
    try:
        file_like = BytesIO(audio_bytes)
        result = supabase_client.storage.from_('meeting').upload(
            storage_path,
            file_like.read(),
            {"content-type": content_type}
        )
        return True
    except Exception as e:
        await channel.send(f"⚠️ Failed to upload audio file: {e}")
        return False


async def upload_metadata(
    data: Dict, 
    meeting_name: str, 
    channel: Union[discord.TextChannel, discord.VoiceChannel]
) -> bool:
    """
    Upload meeting metadata as JSON to Supabase storage.
    
    Args:
        data: Metadata dictionary
        meeting_name: Name of the meeting
        channel: Discord channel for error messages
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert dict → JSON string → bytes
        json_data = json.dumps(data, indent=2).encode('utf-8')
        files_like = BytesIO(json_data)

        storage_path = f'{meeting_name}/{meeting_name}_metadata.json'
        result = supabase_client.storage.from_("meeting").upload(
            storage_path,
            files_like.read(),
        )
        return True
    except Exception as e:
        await channel.send(f"⚠️ Failed to upload metadata: {e}")
        return False


async def upload_text_file(
    text_content: str,
    storage_path: str,
    channel: Union[discord.TextChannel, discord.VoiceChannel],
    content_type: str = "text/plain"
) -> bool:
    """
    Upload text content to Supabase storage.
    
    Args:
        text_content: Text content to upload
        storage_path: Storage path in Supabase
        channel: Discord channel for error messages
        content_type: MIME type of the content
        
    Returns:
        True if successful, False otherwise
    """
    try:
        text_bytes = text_content.encode('utf-8')
        return await upload_audio(text_bytes, storage_path, channel, content_type)
    except Exception as e:
        await channel.send(f"⚠️ Failed to upload text file: {e}")
        return False
    
async def get_transcript(meeting_name: str) -> str:
    """
    Retrieve the full transcript of a meeting from Supabase storage.
    
    Args:
        meeting_name: Name of the meeting
        channel: Discord channel for error messages
        
    Returns:
        Full transcript as a string, or an error message if retrieval fails
    """
    try:
        folder = f"{meeting_name}/text_segments/"
        files_name = supabase_client.storage.from_("meeting").list(folder)
        
        if not files_name:
            return "⚠️ No transcript segments found for this meeting."
        sorted_files = sorted(files_name, key=lambda x: int(x.name.split('.')[0]))
        
        full_transcript = ""
        for file in sorted_files:
            path = folder + file['name']
            file_data = supabase_client.storage.from_("meeting").download(path).decode('utf-8')
            full_transcript += file_data.strip() + "\n"
            
        return full_transcript
        
    except Exception as e:
        return f"⚠️ Failed to retrieve transcript: {e}"


