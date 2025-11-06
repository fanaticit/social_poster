"""
Video Manager - Validates and manages video files
Checks format, resolution, file size, and duration
"""

import os
import subprocess
import json


class VideoManager:
    """Manages video file validation and information"""

    # Platform requirements
    MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4GB
    YOUTUBE_SHORTS_MAX_DURATION = 60  # seconds
    TIKTOK_MAX_DURATION = 600  # 10 minutes in seconds

    SUPPORTED_FORMATS = ['.mp4', '.mov', '.avi', '.mkv']
    RECOMMENDED_RESOLUTION = (1080, 1920)  # width x height for vertical video

    def __init__(self):
        """Initialize video manager"""
        pass

    def validate_video(self, video_file):
        """
        Validate video file for upload

        Args:
            video_file: Path to video file

        Returns:
            Dictionary with validation results and video info
        """
        if not os.path.exists(video_file):
            return {
                'valid': False,
                'error': f"Video file not found: {video_file}"
            }

        # Check file extension
        _, ext = os.path.splitext(video_file)
        if ext.lower() not in self.SUPPORTED_FORMATS:
            return {
                'valid': False,
                'error': f"Unsupported format: {ext}. Supported: {', '.join(self.SUPPORTED_FORMATS)}"
            }

        # Check file size
        file_size = os.path.getsize(video_file)
        if file_size > self.MAX_FILE_SIZE:
            size_gb = file_size / (1024 * 1024 * 1024)
            return {
                'valid': False,
                'error': f"File too large: {size_gb:.2f}GB (max 4GB)"
            }

        # Get video info
        video_info = self._get_video_info(video_file)

        if not video_info:
            return {
                'valid': False,
                'error': "Could not read video information. File may be corrupted."
            }

        # Check duration
        duration = video_info.get('duration', 0)
        if duration > self.TIKTOK_MAX_DURATION:
            return {
                'valid': False,
                'error': f"Video too long: {duration}s (max {self.TIKTOK_MAX_DURATION}s for TikTok)"
            }

        # Warnings for non-optimal settings
        warnings = []
        width = video_info.get('width', 0)
        height = video_info.get('height', 0)

        if (width, height) != self.RECOMMENDED_RESOLUTION:
            warnings.append(
                f"Resolution {width}x{height} differs from recommended {self.RECOMMENDED_RESOLUTION[0]}x{self.RECOMMENDED_RESOLUTION[1]} for vertical video"
            )

        if duration > self.YOUTUBE_SHORTS_MAX_DURATION:
            warnings.append(
                f"Duration {duration}s exceeds YouTube Shorts limit ({self.YOUTUBE_SHORTS_MAX_DURATION}s)"
            )

        return {
            'valid': True,
            'video_info': video_info,
            'warnings': warnings
        }

    def _get_video_info(self, video_file):
        """
        Get video file information using ffprobe

        Args:
            video_file: Path to video file

        Returns:
            Dictionary with video properties
        """
        try:
            # Try using ffprobe (part of ffmpeg)
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_file
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                print(f"Warning: ffprobe not available or failed. Using basic info only.")
                return self._get_basic_info(video_file)

            data = json.loads(result.stdout)

            # Extract video stream info
            video_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break

            if not video_stream:
                return None

            # Extract format info
            format_info = data.get('format', {})

            return {
                'width': int(video_stream.get('width', 0)),
                'height': int(video_stream.get('height', 0)),
                'duration': float(format_info.get('duration', 0)),
                'codec': video_stream.get('codec_name', 'unknown'),
                'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                'bitrate': int(format_info.get('bit_rate', 0)),
                'size': int(format_info.get('size', 0))
            }

        except FileNotFoundError:
            print("Warning: ffprobe not found. Install ffmpeg for full video validation.")
            return self._get_basic_info(video_file)
        except subprocess.TimeoutExpired:
            print("Warning: ffprobe timed out.")
            return self._get_basic_info(video_file)
        except Exception as e:
            print(f"Warning: Error getting video info with ffprobe: {e}")
            return self._get_basic_info(video_file)

    def _get_basic_info(self, video_file):
        """
        Get basic video info without ffprobe

        Args:
            video_file: Path to video file

        Returns:
            Dictionary with basic file info
        """
        return {
            'width': 1080,  # Assume standard
            'height': 1920,
            'duration': 0,  # Unknown
            'codec': 'unknown',
            'fps': 30,
            'bitrate': 0,
            'size': os.path.getsize(video_file)
        }

    def get_file_size_mb(self, video_file):
        """
        Get video file size in MB

        Args:
            video_file: Path to video file

        Returns:
            File size in MB
        """
        if not os.path.exists(video_file):
            return 0

        size_bytes = os.path.getsize(video_file)
        return size_bytes / (1024 * 1024)

    def is_vertical_video(self, video_file):
        """
        Check if video is vertical (height > width)

        Args:
            video_file: Path to video file

        Returns:
            True if vertical, False otherwise
        """
        video_info = self._get_video_info(video_file)
        if not video_info:
            return False

        width = video_info.get('width', 0)
        height = video_info.get('height', 0)

        return height > width
