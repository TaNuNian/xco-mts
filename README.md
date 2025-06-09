# Discord Meeting Transcription Bot

A Discord bot that records voice channel conversations, transcribes them using OpenAI Whisper, generates meeting summaries using GPT, and stores everything in Supabase.

## Features

- 🎙️ **Voice Recording**: Record Discord voice channel conversations
- 📝 **AI Transcription**: Transcribe audio using Whisper model
- 🤖 **Smart Summaries**: Generate meeting summaries in Thai using GPT-4
- ☁️ **Cloud Storage**: Store recordings and metadata in Supabase
- 🎵 **Audio Processing**: Mix multiple audio streams using FFmpeg
- 📊 **Meeting Analytics**: Track duration, participants, and metadata

## Project Structure

```
├── main_refactored.py      # Main entry point
├── config.py               # Configuration and environment setup
├── bot_commands.py         # Discord bot command handlers
├── meeting_recorder.py     # Core meeting recording logic
├── audio_processor.py      # FFmpeg audio processing utilities
├── transcription_service.py # Whisper transcription and OpenAI integration
├── storage_service.py      # Supabase storage operations
├── utils.py               # Common utility functions
└── .env.example          # Environment variables template
```

## Setup

### Prerequisites

- Python 3.8+
- FFmpeg installed on your system
- Discord bot token
- OpenAI API key
- Supabase project

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd xco-mts
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

4. **Configure your environment**
   - `DISCORD_TOKEN`: Your Discord bot token
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_KEY`: Your Supabase anon key

### Running the Bot

```bash
uv run main.py
```

## Usage

### Discord Commands

- `/start` - Start recording in the current voice channel
- `/stop` - Stop recording and process the audio

### What happens when you record:

1. **Recording**: Bot joins voice channel and records all participants
2. **Processing**: Individual audio streams are mixed using FFmpeg
3. **Transcription**: Mixed audio is transcribed using Whisper
4. **Summary**: GPT-4 generates a structured meeting summary in Thai
5. **Storage**: All files are uploaded to Supabase:
   - Individual user recordings
   - Mixed meeting audio
   - Transcription text
   - Meeting metadata JSON

## Architecture

### Modular Design

The bot is designed with separation of concerns:

- **Config Module**: Centralized configuration and client initialization
- **Audio Processor**: Handles FFmpeg operations for mixing and converting audio
- **Transcription Service**: Manages Whisper transcription and OpenAI summarization
- **Storage Service**: Handles all Supabase upload operations
- **Meeting Recorder**: Core business logic for recording sessions
- **Bot Commands**: Discord command interface
- **Utils**: Common utility functions

### Key Classes

- `MeetingRecorder`: Main class handling recording sessions
- Modular functions for audio processing, transcription, and storage

## Thai Language Support

The bot includes a specialized Thai meeting assistant prompt that generates structured summaries with:

- **หัวข้ออภิปราย** (Discussion Topics)
- **งานที่ได้รับมอบหมาย** (Assigned Tasks)
- **เป้าหมายและการตัดสินใจ** (Goals and Decisions)

## Storage Structure

Files are organized in Supabase storage as:
```
meeting_YYYYMMDD_HHMMSS/
├── individuals/
│   ├── user_id_1.mp3
│   └── user_id_2.mp3
├── meeting_mix.mp3
├── transcription.txt
└── meeting_YYYYMMDD_HHMMSS_metadata.json
```

## Error Handling

- Comprehensive error handling with user-friendly Discord messages
- Automatic cleanup of temporary files
- Graceful handling of network and API failures

## Development

### Adding New Features

1. **New Commands**: Add to `bot_commands.py`
2. **Audio Processing**: Extend `audio_processor.py`
3. **Storage Operations**: Add to `storage_service.py`
4. **Business Logic**: Modify `meeting_recorder.py`

### Testing

Each module can be tested independently due to the modular design.

## License

See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes following the modular structure
4. Submit a pull request

## Troubleshooting

### Common Issues

- **FFmpeg not found**: Ensure FFmpeg is installed and in PATH
- **Discord permissions**: Bot needs voice channel permissions
- **Supabase errors**: Check credentials and storage bucket setup
- **OpenAI rate limits**: Monitor API usage and implement retry logic
