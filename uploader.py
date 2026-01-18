"""
Upload Orchestrator - Manages parallel uploads to multiple platforms
Coordinates YouTube and TikTok uploads with error handling
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from oauth_handler import OAuthHandler
from youtube_uploader import YouTubeUploader
from tiktok_uploader import TikTokUploader
from video_manager import VideoManager


class UploadOrchestrator:
    """Orchestrates video uploads to multiple platforms"""

    def __init__(self, config_file='config.json', env_file='.env'):
        """
        Initialize upload orchestrator

        Args:
            config_file: Path to configuration file
            env_file: Path to environment file with secrets
        """
        self.config_file = config_file
        self.config = self._load_config()
        self.oauth_handler = OAuthHandler()
        self.video_manager = VideoManager()

        # Load environment variables
        self._load_env(env_file)

    def _load_config(self):
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Config file not found: {self.config_file}")

        with open(self.config_file, 'r') as f:
            return json.load(f)

    def _load_env(self, env_file):
        """Load environment variables from .env file"""
        if os.path.exists(env_file):
            from dotenv import load_dotenv
            load_dotenv(env_file)

    def upload_from_metadata(self, metadata_file, platforms=None, max_retries=None):
        """
        Upload video based on metadata file

        Args:
            metadata_file: Path to video metadata JSON file
            platforms: List of specific platforms to upload to (None = all)
            max_retries: Maximum retry attempts (None = use config default)

        Returns:
            Dictionary with results for each platform
        """
        # Load metadata
        if not os.path.exists(metadata_file):
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        # Validate video file
        video_file = metadata.get('video_file')
        if not video_file:
            raise ValueError("No video_file specified in metadata")

        print(f"\n{'='*60}")
        print(f"Video Upload Pipeline")
        print(f"{'='*60}")
        print(f"Video: {video_file}")

        validation = self.video_manager.validate_video(video_file)

        if not validation['valid']:
            raise ValueError(f"Video validation failed: {validation['error']}")

        if validation.get('warnings'):
            print("\nWarnings:")
            for warning in validation['warnings']:
                print(f"  - {warning}")

        video_info = validation.get('video_info', {})
        print(f"\nVideo Info:")
        print(f"  Resolution: {video_info.get('width')}x{video_info.get('height')}")
        print(f"  Duration: {video_info.get('duration', 0):.1f}s")
        print(f"  Size: {self.video_manager.get_file_size_mb(video_file):.1f}MB")

        # Determine which platforms to upload to
        target_platforms = platforms if platforms else metadata.get('platforms', [])

        print(f"\nTarget platforms: {', '.join(target_platforms)}")
        print(f"\n{'='*60}\n")

        # Get retry setting
        if max_retries is None:
            max_retries = self.config.get('upload_settings', {}).get('max_retries', 3)

        # Upload to all platforms in parallel
        results = self._parallel_upload(video_file, metadata, target_platforms, max_retries)

        # Log results
        self._log_results(video_file, metadata, results)

        # Display summary
        self._display_summary(results)

        return results

    def _parallel_upload(self, video_file, metadata, platforms, max_retries):
        """
        Upload to multiple platforms in parallel

        Args:
            video_file: Path to video file
            metadata: Video metadata dictionary
            platforms: List of platform identifiers
            max_retries: Maximum retry attempts

        Returns:
            Dictionary with results for each platform
        """
        results = {}

        with ThreadPoolExecutor(max_workers=len(platforms)) as executor:
            futures = {}

            for platform in platforms:
                future = executor.submit(
                    self._upload_to_platform,
                    platform,
                    video_file,
                    metadata,
                    max_retries
                )
                futures[future] = platform

            # Collect results as they complete
            for future in as_completed(futures):
                platform = futures[future]
                try:
                    result = future.result()
                    results[platform] = result
                except Exception as e:
                    results[platform] = {
                        'success': False,
                        'error': str(e),
                        'platform': platform
                    }

        return results

    def _upload_to_platform(self, platform, video_file, metadata, max_retries):
        """
        Upload to a specific platform with retry logic

        Args:
            platform: Platform identifier (e.g., 'youtube_english')
            video_file: Path to video file
            metadata: Video metadata dictionary
            max_retries: Maximum retry attempts

        Returns:
            Upload result dictionary
        """
        # Authenticate ONCE before retries (don't re-auth on each retry)
        try:
            uploader = self._get_authenticated_uploader(platform)
        except Exception as e:
            return {
                'success': False,
                'error': f"Authentication failed: {str(e)}",
                'platform': platform
            }

        # Attempt upload once (no retries)
        try:
            result = self._do_upload_with_uploader(platform, video_file, metadata, uploader)
            return result

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'platform': platform
            }

    def _get_authenticated_uploader(self, platform):
        """
        Get authenticated uploader for a platform (auth happens once here)

        Args:
            platform: Platform identifier

        Returns:
            Tuple of (uploader, platform_type, language, lang_metadata)
        """
        parts = platform.split('_')
        platform_type = parts[0]  # 'youtube' or 'tiktok'
        language = parts[1] if len(parts) > 1 else 'english'

        if platform_type == 'youtube':
            account_config = self.config['accounts']['youtube'][language]
            credentials = self.oauth_handler.get_youtube_credentials(
                language,
                account_config['token_file']
            )
            from youtube_uploader import YouTubeUploader
            return (YouTubeUploader(credentials), platform_type, language)

        elif platform_type == 'tiktok':
            account_config = self.config['accounts']['tiktok'][language]
            client_key = os.getenv('TIKTOK_CLIENT_ID')
            client_secret = os.getenv('TIKTOK_CLIENT_SECRET')

            if not client_key or not client_secret:
                raise ValueError('TikTok credentials not found in .env file')

            token_data = self.oauth_handler.get_tiktok_credentials(
                language,
                account_config['token_file'],
                client_key,
                client_secret
            )

            access_token = token_data.get('access_token')
            if not access_token:
                raise ValueError('Failed to get TikTok access token')

            from tiktok_uploader import TikTokUploader
            return (TikTokUploader(access_token), platform_type, language)

        else:
            raise ValueError(f"Unknown platform type: {platform_type}")

    def _do_upload_with_uploader(self, platform, video_file, metadata, uploader_tuple):
        """
        Perform actual upload using pre-authenticated uploader

        Args:
            platform: Platform identifier
            video_file: Path to video file (default, can be overridden by language-specific file)
            metadata: Video metadata dictionary
            uploader_tuple: Tuple from _get_authenticated uploader

        Returns:
            Upload result dictionary
        """
        uploader, platform_type, language = uploader_tuple
        lang_metadata = metadata.get(language, {})

        # Use language-specific video file if specified, otherwise use default
        if 'video_file' in lang_metadata:
            video_file = lang_metadata['video_file']
            print(f"Using language-specific video file: {video_file}")

        if platform_type == 'youtube':
            category_id = self.config.get('upload_settings', {}).get('youtube_category', '20')
            privacy = self.config.get('upload_settings', {}).get('video_privacy', 'public')

            # Combine description with YouTube hashtags
            description = lang_metadata.get('description', '')
            youtube_hashtags = lang_metadata.get('youtube_hashtags', '')
            if youtube_hashtags:
                full_description = f"{description}\n\n{youtube_hashtags}".strip()
            else:
                full_description = description

            result = uploader.upload_video(
                video_file=video_file,
                title=lang_metadata.get('title', 'Untitled'),
                description=full_description,
                tags=lang_metadata.get('tags', []),
                category_id=category_id,
                privacy_status=privacy
            )
            result['account'] = language
            return result

        elif platform_type == 'tiktok':
            title = lang_metadata.get('title', 'Untitled')
            hashtags = lang_metadata.get('tiktok_hashtags', '')
            caption = f"{title} {hashtags}".strip()

            result = uploader.upload_video(
                video_file=video_file,
                title=caption,
                description=lang_metadata.get('description', ''),
                privacy_level='SELF_ONLY'  # Sandbox apps can only post private videos
            )
            result['account'] = language
            return result

    def _do_upload(self, platform, video_file, metadata):
        """
        Perform actual upload to platform (OLD METHOD - kept for compatibility)

        Args:
            platform: Platform identifier
            video_file: Path to video file
            metadata: Video metadata dictionary

        Returns:
            Upload result dictionary
        """
        parts = platform.split('_')
        platform_type = parts[0]  # 'youtube' or 'tiktok'
        language = parts[1] if len(parts) > 1 else 'english'  # 'english' or 'japanese'

        # Get language-specific metadata
        lang_metadata = metadata.get(language, {})

        if platform_type == 'youtube':
            return self._upload_to_youtube(language, video_file, lang_metadata)
        elif platform_type == 'tiktok':
            return self._upload_to_tiktok(language, video_file, lang_metadata)
        else:
            raise ValueError(f"Unknown platform type: {platform_type}")

    def _upload_to_youtube(self, account_name, video_file, metadata):
        """Upload to YouTube account"""
        account_config = self.config['accounts']['youtube'][account_name]

        # Get credentials
        credentials = self.oauth_handler.get_youtube_credentials(
            account_name,
            account_config['token_file']
        )

        # Create uploader
        uploader = YouTubeUploader(credentials)

        # Upload
        category_id = self.config.get('upload_settings', {}).get('youtube_category', '20')
        privacy = self.config.get('upload_settings', {}).get('video_privacy', 'public')

        result = uploader.upload_video(
            video_file=video_file,
            title=metadata.get('title', 'Untitled'),
            description=metadata.get('description', ''),
            tags=metadata.get('tags', []),
            category_id=category_id,
            privacy_status=privacy
        )

        result['account'] = account_name
        return result

    def _upload_to_tiktok(self, account_name, video_file, metadata):
        """Upload to TikTok account"""
        account_config = self.config['accounts']['tiktok'][account_name]

        # Get credentials
        client_key = os.getenv('TIKTOK_CLIENT_ID')
        client_secret = os.getenv('TIKTOK_CLIENT_SECRET')

        if not client_key or not client_secret:
            return {
                'success': False,
                'error': 'TikTok credentials not found in .env file',
                'platform': 'tiktok',
                'account': account_name
            }

        token_data = self.oauth_handler.get_tiktok_credentials(
            account_name,
            account_config['token_file'],
            client_key,
            client_secret
        )

        # Create uploader
        access_token = token_data.get('access_token')
        if not access_token:
            return {
                'success': False,
                'error': 'Failed to get TikTok access token',
                'platform': 'tiktok',
                'account': account_name
            }

        uploader = TikTokUploader(access_token)

        # Combine title and hashtags
        title = metadata.get('title', 'Untitled')
        hashtags = metadata.get('hashtags', '')
        caption = f"{title} {hashtags}".strip()

        # Upload
        result = uploader.upload_video(
            video_file=video_file,
            title=caption,
            description=metadata.get('description', ''),
            privacy_level='SELF_ONLY'  # Sandbox apps can only post private videos
        )

        result['account'] = account_name
        return result

    def _log_results(self, video_file, metadata, results):
        """
        Log upload results to file

        Args:
            video_file: Path to video file
            metadata: Video metadata
            results: Upload results dictionary
        """
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / 'upload_log.txt'

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with open(log_file, 'a') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Upload Log - {timestamp}\n")
            f.write(f"{'='*80}\n")
            f.write(f"Video: {video_file}\n")
            f.write(f"Title (EN): {metadata.get('english', {}).get('title', 'N/A')}\n")
            f.write(f"Title (JP): {metadata.get('japanese', {}).get('title', 'N/A')}\n")
            f.write(f"\nResults:\n")

            for platform, result in results.items():
                f.write(f"\n  {platform}:\n")
                if result['success']:
                    f.write(f"    Status: SUCCESS\n")
                    if 'video_url' in result:
                        f.write(f"    URL: {result['video_url']}\n")
                    if 'video_id' in result:
                        f.write(f"    ID: {result['video_id']}\n")
                    if 'publish_id' in result:
                        f.write(f"    Publish ID: {result['publish_id']}\n")
                else:
                    f.write(f"    Status: FAILED\n")
                    f.write(f"    Error: {result.get('error', 'Unknown error')}\n")

            f.write(f"\n{'='*80}\n")

    def _display_summary(self, results):
        """
        Display upload results summary

        Args:
            results: Upload results dictionary
        """
        print(f"\n{'='*60}")
        print("Upload Summary")
        print(f"{'='*60}\n")

        success_count = sum(1 for r in results.values() if r.get('success'))
        total_count = len(results)

        for platform, result in results.items():
            status = "SUCCESS" if result.get('success') else "FAILED"
            icon = "✓" if result.get('success') else "✗"

            print(f"{icon} {platform}: {status}")

            if result.get('success'):
                if 'video_url' in result:
                    print(f"  URL: {result['video_url']}")
                if 'publish_id' in result:
                    print(f"  Publish ID: {result['publish_id']}")
            else:
                print(f"  Error: {result.get('error', 'Unknown error')}")

            print()

        print(f"{'='*60}")
        print(f"Total: {success_count}/{total_count} successful")
        print(f"{'='*60}\n")
