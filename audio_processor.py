"""Audio processing utilities using FFmpeg."""

import subprocess
import tempfile
import os
from typing import List


def ffmpeg_mix_audio_streams(audio_streams: List[bytes], output_format: str = "mp3") -> bytes:
    """
    Mix multiple audio streams into a single audio file using FFmpeg.
    
    Args:
        audio_streams: List of audio data as bytes
        output_format: Output format (default: "mp3")
        
    Returns:
        Mixed audio data as bytes
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
            except OSError:
                pass


def ffmpeg_convert_audio(audio_data: bytes, output_format: str = "mp3", **kwargs) -> bytes:
    """
    Convert audio data to a different format using FFmpeg.
    
    Args:
        audio_data: Input audio data as bytes
        output_format: Output format (default: "mp3")
        **kwargs: Additional FFmpeg arguments
        
    Returns:
        Converted audio data as bytes
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
