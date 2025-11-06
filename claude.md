# Multi-Platform Video Upload Pipeline

## Project Overview
A local macOS application that automates uploading AI-generated videos to multiple social media platforms (YouTube and TikTok) simultaneously. The tool reads video metadata and hashtags from a configuration file and uploads to English and Japanese accounts on both platforms.

## Target Use Case
- Quick publishing when game news drops
- Same video content to YouTube Shorts and TikTok
- Separate English and Japanese versions
- No scheduling - immediate upload when videos are ready
- Local-only operation (no cloud dependencies)

## Features
1. Read video metadata from a text/JSON configuration file
2. Support multiple platform accounts (YouTube English/Japanese, TikTok English/Japanese)
3. Platform-specific hashtags and descriptions
4. Parallel uploads to all platforms simultaneously
5. Error handling and retry logic
6. Secure OAuth token storage locally
7. Simple CLI interface
8. Logging of upload results

## Technology Stack
- **Language:** Python 3.9+
- **APIs:** YouTube Data API v3, TikTok Content Posting API
- **Libraries:**
  - `google-auth-oauthlib` - YouTube authentication
  - `google-auth-httplib2` - YouTube API
  - `google-api-python-client` - YouTube client
  - `requests` - HTTP requests for TikTok API
  - `python-dotenv` - Environment variable management
  - `concurrent.futures` - Parallel uploads

## Installation & Setup

### Prerequisites
- Python 3.9 or higher
- macOS (tested on Apple Silicon)
- Your YouTube and TikTok creator accounts ready
- OAuth credentials set up on Google Cloud and TikTok developer platforms

### Initial Setup Steps
1. Clone/create the project directory
2. Create virtual environment: `python -m venv venv`
3. Activate: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Set up API credentials (see API Setup section)
6. Run: `python main.py`

### API Setup Instructions

#### YouTube Data API
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable "YouTube Data API v3"
4. Create OAuth 2.0 credentials (Desktop app)
5. Download credentials as JSON
6. Save as `credentials/youtube_credentials.json`
7. First run will open browser for OAuth consent

#### TikTok Content Posting API
1. Go to [TikTok Developer Portal](https://developers.tiktok.com/)
2. Create an application
3. Request access to "Video Upload" scope
4. Get Client ID and Client Secret
5. Create `.env` file in project root with:
   ```
   TIKTOK_CLIENT_ID=your_client_id
   TIKTOK_CLIENT_SECRET=your_client_secret
   ```

## Project Structure
```
video-upload-pipeline/
├── main.py                 # Entry point
├── config.json            # User configuration (account IDs, channel mappings)
├── video_metadata.json    # Video info for current upload
├── requirements.txt       # Python dependencies
├── .env                   # API secrets (not in git)
├── .gitignore            # Ignore credentials and tokens
├── credentials/
│   ├── youtube_tokens/   # YouTube OAuth tokens per account
│   └── tiktok_tokens/    # TikTok OAuth tokens per account
├── logs/
│   └── upload_log.txt    # Upload history and results
└── videos/
    └── (local video files)
```

## Configuration Files

### config.json
```json
{
  "accounts": {
    "youtube": {
      "english": {
        "channel_id": "YOUR_ENGLISH_CHANNEL_ID",
        "token_file": "credentials/youtube_tokens/english_token.json"
      },
      "japanese": {
        "channel_id": "YOUR_JAPANESE_CHANNEL_ID",
        "token_file": "credentials/youtube_tokens/japanese_token.json"
      }
    },
    "tiktok": {
      "english": {
        "user_id": "YOUR_ENGLISH_TIKTOK_USER_ID",
        "token_file": "credentials/tiktok_tokens/english_token.json"
      },
      "japanese": {
        "user_id": "YOUR_JAPANESE_TIKTOK_USER_ID",
        "token_file": "credentials/tiktok_tokens/japanese_token.json"
      }
    }
  },
  "upload_settings": {
    "video_privacy": "PUBLIC",
    "youtube_category": "24",
    "max_retries": 3
  }
}
```

### video_metadata.json
```json
{
  "video_file": "videos/game_news_nov6.mp4",
  "english": {
    "title": "New Character Announcement - Game Title",
    "description": "Exciting news! Check out the new character coming to Game Title. Subscribe for more updates!",
    "tags": ["game", "gaming", "announcement", "newcharacter"],
    "hashtags": "#gaming #gamesnews #newcharacter #gameannouncement"
  },
  "japanese": {
    "title": "新キャラクター発表 - ゲームタイトル",
    "description": "新しいキャラクターがゲームタイトルに登場します。詳細はビデオをチェック！",
    "tags": ["ゲーム", "ゲーム実況", "発表", "新キャラ"],
    "hashtags": "#ゲーム #ゲーム動画 #新キャラ #ゲーム発表"
  },
  "platforms": ["youtube_english", "youtube_japanese", "tiktok_english", "tiktok_japanese"]
}
```

## Usage

### Basic Upload
```bash
python main.py --config config.json --metadata video_metadata.json
```

### First Time Setup (Interactive)
```bash
python main.py --setup
```

### Upload to Specific Platforms
```bash
python main.py --metadata video_metadata.json --platforms youtube_english tiktok_english
```

### View Upload History
```bash
python main.py --logs
```

## Implementation Details

### Main Components

**1. OAuth Handler (`oauth_handler.py`)**
- Manages authentication for YouTube and TikTok
- Stores tokens locally and refreshes when expired
- Handles OAuth consent flow on first run
- Supports multiple accounts per platform

**2. YouTube Uploader (`youtube_uploader.py`)**
- Uploads video to YouTube
- Sets title, description, tags, privacy settings
- Handles video processing queue
- Returns video URL after successful upload

**3. TikTok Uploader (`tiktok_uploader.py`)**
- Uploads video to TikTok
- Sets caption with hashtags
- Handles TikTok's video format requirements
- Returns video URL after successful upload

**4. Video Manager (`video_manager.py`)**
- Validates video files locally
- Checks video format and resolution
- Resizes/converts if needed for platform requirements
- Validates file size limits

**5. Upload Orchestrator (`uploader.py`)**
- Reads metadata from JSON
- Orchestrates parallel uploads using ThreadPoolExecutor
- Handles errors per platform independently
- Logs all results

**6. Main CLI (`main.py`)**
- Entry point with argument parsing
- Loads configuration
- Calls appropriate functions based on args
- Displays results to user

### Error Handling
- Individual platform failures don't stop other uploads
- Automatic retry logic (configurable, default 3 times)
- Detailed error logging for debugging
- User-friendly error messages

### Video Specifications
- **Format:** MP4 (H.264/H.265 video, AAC audio)
- **Resolution:** 1080x1920 (vertical for TikTok/Shorts)
- **YouTube Shorts:** Up to 60 seconds
- **TikTok:** Up to 10 minutes
- **Max file size:** 4GB

## Workflow Example
1. User creates/generates video files locally
2. Creates `video_metadata.json` with titles, descriptions, hashtags
3. Runs: `python main.py --metadata video_metadata.json`
4. Application authenticates (first time only)
5. Validates video file
6. Uploads to all 4 accounts in parallel
7. Displays results with video URLs
8. Logs upload to `logs/upload_log.txt`

## Future Enhancements
- GUI interface using PyQt or Tkinter
- Batch upload multiple videos
- Schedule uploads for later
- Analytics integration to track video performance
- Thumbnail auto-generation
- Video preprocessing/optimization

## Troubleshooting
- **"Authentication failed"**: Delete token files and run with `--setup`
- **"Video format not supported"**: Check resolution is 1080x1920 vertical
- **"Rate limit exceeded"**: Wait 5 minutes before retrying
- **Platform upload fails but not others**: Check platform-specific requirements in logs

## Security Notes
- OAuth tokens stored locally, never transmitted
- Use `.env` file for secrets, never commit to git
- Credentials should be kept private
- Regularly review app permissions on platform dashboards
