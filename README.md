# Multi-Platform Video Upload Pipeline

A local macOS application that automates uploading AI-generated videos to multiple social media platforms (YouTube and TikTok) simultaneously. Perfect for quick publishing when game news drops, supporting both English and Japanese accounts.

## Features

- Upload videos to multiple platforms simultaneously (YouTube & TikTok)
- Support for English and Japanese accounts on each platform
- Platform-specific metadata (titles, descriptions, hashtags)
- Parallel uploads for maximum efficiency
- Automatic retry logic with error handling
- Secure OAuth token storage locally
- Simple CLI interface
- Comprehensive logging of upload results
- Video validation before upload

## Prerequisites

- Python 3.9 or higher
- macOS (tested on Apple Silicon)
- YouTube and TikTok creator accounts
- OAuth credentials from Google Cloud Console and TikTok Developer Portal

## Quick Start

### 1. Installation

```bash
# Clone or navigate to the project directory
cd social_poster

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. API Setup

#### YouTube Data API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable "YouTube Data API v3"
4. Create OAuth 2.0 credentials (Desktop app)
5. Download credentials JSON
6. Save as `credentials/youtube_credentials.json`

#### TikTok Content Posting API

1. Go to [TikTok Developer Portal](https://developers.tiktok.com/)
2. Create an application
3. Request access to "Video Upload" scope
4. Copy your Client ID and Client Secret
5. You'll add these in the next step

### 3. Configuration

Run the interactive setup:

```bash
python main.py --setup
```

This will:
- Create a `config.json` file with your account settings
- Create a `.env` file for TikTok credentials
- Set up the directory structure

Alternatively, manually copy the example files:

```bash
cp config.json.example config.json
cp video_metadata.json.example video_metadata.json
cp .env.example .env
```

Then edit these files with your actual credentials and account information.

### 4. First Upload

1. Place your video in the `videos/` directory
2. Create a metadata file (or use the example):

```json
{
  "video_file": "videos/your_video.mp4",
  "english": {
    "title": "Your Video Title",
    "description": "Your description here",
    "tags": ["tag1", "tag2"],
    "hashtags": "#hashtag1 #hashtag2"
  },
  "japanese": {
    "title": "ビデオタイトル",
    "description": "説明",
    "tags": ["タグ1", "タグ2"],
    "hashtags": "#ハッシュタグ1 #ハッシュタグ2"
  },
  "platforms": ["youtube_english", "youtube_japanese", "tiktok_english", "tiktok_japanese"]
}
```

3. Run the upload:

```bash
python main.py --metadata video_metadata.json
```

On first run, a browser window will open for OAuth authentication for each platform.

## Usage

### Basic Upload

Upload to all configured platforms:

```bash
python main.py --metadata video_metadata.json
```

### Upload to Specific Platforms

```bash
python main.py --metadata video_metadata.json --platforms youtube_english tiktok_english
```

### Validate Video Before Upload

```bash
python main.py --validate videos/your_video.mp4
```

### View Upload History

```bash
python main.py --logs
```

### Set Custom Retry Count

```bash
python main.py --metadata video_metadata.json --retries 5
```

## Project Structure

```
social_poster/
├── main.py                          # CLI entry point
├── oauth_handler.py                 # OAuth authentication
├── youtube_uploader.py              # YouTube upload logic
├── tiktok_uploader.py               # TikTok upload logic
├── video_manager.py                 # Video validation
├── uploader.py                      # Upload orchestration
├── config.json                      # Account configuration
├── video_metadata.json              # Video metadata
├── requirements.txt                 # Python dependencies
├── .env                             # API secrets (not in git)
├── .gitignore                       # Git ignore rules
├── credentials/
│   ├── youtube_credentials.json     # YouTube OAuth client
│   ├── youtube_tokens/              # YouTube access tokens
│   └── tiktok_tokens/               # TikTok access tokens
├── logs/
│   └── upload_log.txt               # Upload history
└── videos/
    └── (your video files here)
```

## Video Specifications

- **Format:** MP4 (H.264/H.265 video, AAC audio)
- **Resolution:** 1080x1920 (vertical for TikTok/Shorts)
- **YouTube Shorts:** Up to 60 seconds
- **TikTok:** Up to 10 minutes
- **Max file size:** 4GB

## Configuration Files

### config.json

Stores account information and upload settings:

```json
{
  "accounts": {
    "youtube": {
      "english": {
        "channel_id": "YOUR_CHANNEL_ID",
        "token_file": "credentials/youtube_tokens/english_token.json"
      }
    },
    "tiktok": {
      "english": {
        "user_id": "YOUR_USER_ID",
        "token_file": "credentials/tiktok_tokens/english_token.json"
      }
    }
  },
  "upload_settings": {
    "video_privacy": "PUBLIC",
    "youtube_category": "20",
    "max_retries": 3
  }
}
```

### video_metadata.json

Stores metadata for each video upload:

- `video_file`: Path to the video file
- `english`: English language metadata (title, description, tags, hashtags)
- `japanese`: Japanese language metadata
- `platforms`: List of platforms to upload to

## Troubleshooting

### Authentication Issues

**Problem:** "Authentication failed" or expired tokens

**Solution:**
```bash
# Delete token files and re-authenticate
rm credentials/youtube_tokens/*
rm credentials/tiktok_tokens/*
python main.py --setup
```

### Video Format Issues

**Problem:** "Video format not supported"

**Solution:** Ensure your video is:
- MP4 format
- 1080x1920 resolution (vertical)
- Under 4GB file size
- Under 10 minutes duration

You can validate your video first:
```bash
python main.py --validate videos/your_video.mp4
```

### Rate Limit Errors

**Problem:** "Rate limit exceeded"

**Solution:** Wait 5-10 minutes before retrying. YouTube and TikTok have rate limits on API calls.

### Platform-Specific Failures

**Problem:** One platform fails but others succeed

**Solution:** Check the logs for detailed error messages:
```bash
python main.py --logs
```

The application is designed to continue uploading to other platforms even if one fails.

## Security Notes

- OAuth tokens are stored locally and never transmitted
- Keep your `.env` file private and never commit to git
- Store credentials securely
- Regularly review app permissions on platform dashboards
- The `.gitignore` file is configured to exclude sensitive files

## Development

### Adding New Platforms

To add support for additional platforms:

1. Create a new uploader class (e.g., `instagram_uploader.py`)
2. Implement OAuth flow in `oauth_handler.py`
3. Add platform configuration to `config.json`
4. Update `uploader.py` to handle the new platform
5. Update metadata format to include new platform

### Running Tests

```bash
# Validate a test video
python main.py --validate videos/test.mp4

# Dry run with metadata
python main.py --metadata video_metadata.json --platforms youtube_english
```

## Contributing

This is a local tool designed for personal use. Feel free to fork and customize for your needs.

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
- Check the Troubleshooting section above
- Review upload logs: `python main.py --logs`
- Validate your video files before uploading
- Ensure all API credentials are correctly configured

## Workflow Example

1. Generate or create your video content
2. Save video to `videos/` directory
3. Create `video_metadata.json` with titles and descriptions
4. Run: `python main.py --metadata video_metadata.json`
5. Application authenticates (first time only)
6. Video is validated
7. Uploads to all platforms in parallel
8. Results displayed with video URLs
9. Upload logged to `logs/upload_log.txt`

## Future Enhancements

Potential features for future versions:
- GUI interface
- Batch upload multiple videos
- Schedule uploads for later
- Analytics integration
- Automatic thumbnail generation
- Video preprocessing/optimization
- Instagram and Facebook support
- Twitter/X video support
