#!/usr/bin/env python3
"""
Multi-Platform Video Upload Pipeline
Main CLI entry point
"""

import argparse
import sys
import os
from pathlib import Path

from uploader import UploadOrchestrator
from video_manager import VideoManager


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description='Multi-Platform Video Upload Pipeline - Upload videos to YouTube and TikTok',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --metadata video_metadata.json
  %(prog)s --metadata video_metadata.json --platforms youtube_english tiktok_english
  %(prog)s --setup
  %(prog)s --logs
        """
    )

    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )

    parser.add_argument(
        '--metadata',
        help='Path to video metadata JSON file'
    )

    parser.add_argument(
        '--platforms',
        nargs='+',
        help='Specific platforms to upload to (e.g., youtube_english tiktok_japanese)'
    )

    parser.add_argument(
        '--setup',
        action='store_true',
        help='Run interactive setup to configure accounts'
    )

    parser.add_argument(
        '--logs',
        action='store_true',
        help='View upload history logs'
    )

    parser.add_argument(
        '--validate',
        help='Validate a video file without uploading'
    )

    parser.add_argument(
        '--retries',
        type=int,
        help='Maximum number of retry attempts per platform'
    )

    args = parser.parse_args()

    # Handle different commands
    if args.setup:
        run_setup()
    elif args.logs:
        view_logs()
    elif args.validate:
        validate_video(args.validate)
    elif args.metadata:
        upload_video(args.config, args.metadata, args.platforms, args.retries)
    else:
        parser.print_help()
        sys.exit(1)


def run_setup():
    """Run interactive setup"""
    print("\n" + "="*60)
    print("Multi-Platform Video Upload Pipeline - Setup")
    print("="*60 + "\n")

    print("This setup wizard will help you configure your accounts.")
    print("\nPrerequisites:")
    print("  1. YouTube OAuth credentials (youtube_credentials.json)")
    print("  2. TikTok Client ID and Client Secret")
    print("  3. Your channel/account IDs for each platform\n")

    # Check for existing config
    config_file = 'config.json'
    if os.path.exists(config_file):
        response = input(f"{config_file} already exists. Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Setup cancelled.")
            return

    # Create config template
    config = {
        "accounts": {
            "youtube": {
                "english": {
                    "channel_id": "",
                    "token_file": "credentials/youtube_tokens/english_token.json"
                },
                "japanese": {
                    "channel_id": "",
                    "token_file": "credentials/youtube_tokens/japanese_token.json"
                }
            },
            "tiktok": {
                "english": {
                    "user_id": "",
                    "token_file": "credentials/tiktok_tokens/english_token.json"
                },
                "japanese": {
                    "user_id": "",
                    "token_file": "credentials/tiktok_tokens/japanese_token.json"
                }
            }
        },
        "upload_settings": {
            "video_privacy": "PUBLIC",
            "youtube_category": "20",
            "max_retries": 3
        }
    }

    # Get YouTube channel IDs
    print("\n--- YouTube Configuration ---")
    config["accounts"]["youtube"]["english"]["channel_id"] = input(
        "Enter English YouTube channel ID (or leave blank): "
    ).strip()
    config["accounts"]["youtube"]["japanese"]["channel_id"] = input(
        "Enter Japanese YouTube channel ID (or leave blank): "
    ).strip()

    # Get TikTok user IDs
    print("\n--- TikTok Configuration ---")
    config["accounts"]["tiktok"]["english"]["user_id"] = input(
        "Enter English TikTok user ID (or leave blank): "
    ).strip()
    config["accounts"]["tiktok"]["japanese"]["user_id"] = input(
        "Enter Japanese TikTok user ID (or leave blank): "
    ).strip()

    # Get upload settings
    print("\n--- Upload Settings ---")
    privacy = input("Default video privacy (PUBLIC/PRIVATE/UNLISTED) [PUBLIC]: ").strip().upper()
    if privacy in ['PUBLIC', 'PRIVATE', 'UNLISTED']:
        config["upload_settings"]["video_privacy"] = privacy

    category = input("YouTube category ID (20=Gaming, 24=Entertainment) [20]: ").strip()
    if category:
        config["upload_settings"]["youtube_category"] = category

    # Save config
    import json
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\n✓ Configuration saved to {config_file}")

    # Check for credentials
    print("\n--- Checking Credentials ---")

    youtube_creds = 'credentials/youtube_credentials.json'
    if not os.path.exists(youtube_creds):
        print(f"✗ YouTube credentials not found at {youtube_creds}")
        print("  Please download OAuth credentials from Google Cloud Console")
    else:
        print(f"✓ YouTube credentials found")

    # Create .env template if it doesn't exist
    env_file = '.env'
    if not os.path.exists(env_file):
        with open(env_file, 'w') as f:
            f.write("# TikTok API Credentials\n")
            f.write("TIKTOK_CLIENT_ID=your_client_id_here\n")
            f.write("TIKTOK_CLIENT_SECRET=your_client_secret_here\n")
        print(f"✓ Created {env_file} template - Please add your TikTok credentials")
    else:
        print(f"✓ {env_file} exists")

    print("\n" + "="*60)
    print("Setup complete!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Add your TikTok credentials to .env")
    print("  2. Place your videos in the videos/ directory")
    print("  3. Create a video_metadata.json file")
    print("  4. Run: python main.py --metadata video_metadata.json\n")


def view_logs():
    """View upload history logs"""
    log_file = 'logs/upload_log.txt'

    if not os.path.exists(log_file):
        print(f"\nNo upload logs found at {log_file}\n")
        return

    print("\n" + "="*60)
    print("Upload History")
    print("="*60 + "\n")

    with open(log_file, 'r') as f:
        content = f.read()
        print(content)


def validate_video(video_file):
    """Validate a video file"""
    print("\n" + "="*60)
    print(f"Validating: {video_file}")
    print("="*60 + "\n")

    manager = VideoManager()
    validation = manager.validate_video(video_file)

    if validation['valid']:
        print("✓ Video is valid for upload\n")

        video_info = validation.get('video_info', {})
        print("Video Information:")
        print(f"  Resolution: {video_info.get('width')}x{video_info.get('height')}")
        print(f"  Duration: {video_info.get('duration', 0):.1f} seconds")
        print(f"  Codec: {video_info.get('codec', 'unknown')}")
        print(f"  Size: {manager.get_file_size_mb(video_file):.1f} MB")
        print(f"  Vertical: {'Yes' if manager.is_vertical_video(video_file) else 'No'}")

        if validation.get('warnings'):
            print("\nWarnings:")
            for warning in validation['warnings']:
                print(f"  ⚠ {warning}")
    else:
        print(f"✗ Validation failed: {validation['error']}")

    print()


def upload_video(config_file, metadata_file, platforms, max_retries):
    """Upload video to platforms"""
    try:
        orchestrator = UploadOrchestrator(config_file)
        results = orchestrator.upload_from_metadata(
            metadata_file,
            platforms=platforms,
            max_retries=max_retries
        )

        # Exit with error code if any uploads failed
        failed = any(not r.get('success') for r in results.values())
        sys.exit(1 if failed else 0)

    except FileNotFoundError as e:
        print(f"\nError: {e}\n")
        sys.exit(1)
    except ValueError as e:
        print(f"\nError: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
