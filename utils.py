"""Utility functions for the meeting transcription bot."""

from datetime import datetime
from typing import List


def generate_meeting_name(timestamp: datetime = None) -> str:
    """
    Generate a unique meeting name based on timestamp.
    
    Args:
        timestamp: Optional timestamp, defaults to current time
        
    Returns:
        Formatted meeting name string
    """
    if timestamp is None:
        timestamp = datetime.now()
    return timestamp.strftime("meeting_%Y%m%d_%H%M%S")


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to a human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def format_user_mentions(user_ids: List[str]) -> str:
    """
    Format user IDs into Discord mentions.
    
    Args:
        user_ids: List of user ID strings
        
    Returns:
        Comma-separated user mentions
    """
    mentions = [f"<@{user_id}>" for user_id in user_ids]
    return ", ".join(mentions)


def truncate_text(text: str, max_length: int = 500) -> str:
    """
    Truncate text to specified length with ellipsis.
    
    Args:
        text: Text to truncate
        max_length: Maximum length (default: 500)
        
    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
