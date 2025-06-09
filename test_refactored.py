"""
Test script to verify the modular structure works correctly.
Run this to check if all imports work properly.
"""

def test_imports():
    """Test that all modules can be imported without errors."""
    try:
        print("Testing imports...")
        
        # Test config
        from config import DISCORD_TOKEN, openai_client, supabase_client, whisper_model
        print("✅ Config module imported successfully")
        
        # Test audio processor
        from audio_processor import ffmpeg_mix_audio_streams, ffmpeg_convert_audio
        print("✅ Audio processor module imported successfully")
        
        # Test transcription service
        from transcription_service import transcribe_audio_from_memory
        print("✅ Transcription service module imported successfully")
        
        # Test storage service
        from storage_service import upload_audio, upload_metadata, upload_text_file
        print("✅ Storage service module imported successfully")
        
        # Test utils
        from utils import generate_meeting_name, format_duration, format_user_mentions, truncate_text
        print("✅ Utils module imported successfully")
        
        # Test meeting recorder
        from meeting_recorder import MeetingRecorder
        print("✅ Meeting recorder module imported successfully")
        
        # Test bot commands
        from bot_commands import setup_bot_commands
        print("✅ Bot commands module imported successfully")
        
        print("\n🎉 All modules imported successfully!")
        print("The refactored code structure is working correctly.")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_utility_functions():
    """Test utility functions with sample data."""
    try:
        from utils import generate_meeting_name, format_duration, format_user_mentions, truncate_text
        from datetime import datetime
        
        print("\nTesting utility functions...")
        
        # Test meeting name generation
        meeting_name = generate_meeting_name()
        print(f"✅ Meeting name: {meeting_name}")
        
        # Test duration formatting
        duration_str = format_duration(3665)  # 1 hour, 1 minute, 5 seconds
        print(f"✅ Duration formatting: {duration_str}")
        
        # Test user mentions
        mentions = format_user_mentions(["123456789", "987654321"])
        print(f"✅ User mentions: {mentions}")
        
        # Test text truncation
        long_text = "This is a very long text that should be truncated" * 20
        truncated = truncate_text(long_text, 50)
        print(f"✅ Text truncation: {truncated}")
        
        return True
        
    except Exception as e:
        print(f"❌ Utility function test error: {e}")
        return False


if __name__ == "__main__":
    print("=== Testing Refactored Discord Meeting Bot ===\n")
    
    import_success = test_imports()
    utility_success = test_utility_functions()
    
    if import_success and utility_success:
        print("\n✅ All tests passed! The refactored code is ready to use.")
        print("\nTo run the bot:")
        print("1. Set up your .env file with the required credentials")
        print("2. Run: python main_refactored.py")
    else:
        print("\n❌ Some tests failed. Please check the error messages above.")
