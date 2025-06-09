"""Transcription service using Whisper and OpenAI."""

import tempfile
import os
from openai.types.chat import ChatCompletion
from faster_whisper import WhisperModel
from config import openai_client, MEETING_ASSISTANT_PROMPT


async def transcribe_audio_from_memory(audio_data: bytes, model: WhisperModel) -> ChatCompletion:
    """
    Transcribe audio data and create a meeting summary using OpenAI.
    
    Args:
        audio_data: Audio data as bytes
        model: WhisperModel instance for transcription
        
    Returns:
        OpenAI ChatCompletion response with meeting summary
    """
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
        temp_file.write(audio_data)
        temp_file.flush()

        try:
            # Transcribe using Whisper
            segments, _ = model.transcribe(temp_file.name, beam_size=5)
            transcription = "\n".join([segment.text for segment in segments])

            # Generate meeting summary using OpenAI
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": MEETING_ASSISTANT_PROMPT},
                    {"role": "user", "content": f"Please summarize the following transcription:\n{transcription}"}
                ],
                temperature=0.3
            )
            return response
            
        finally:
            os.unlink(temp_file.name)
