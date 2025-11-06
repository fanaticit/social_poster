"""
TikTok Uploader - Handles video uploads to TikTok
Uses TikTok Content Posting API v2
"""

import os
import requests
import time
import json


class TikTokUploader:
    """Handles uploading videos to TikTok"""

    # TikTok API endpoints
    POST_VIDEO_INIT_URL = 'https://open.tiktokapis.com/v2/post/publish/video/init/'
    POST_VIDEO_URL = 'https://open.tiktokapis.com/v2/post/publish/video/'
    QUERY_VIDEO_STATUS_URL = 'https://open.tiktokapis.com/v2/post/publish/status/fetch/'

    def __init__(self, access_token):
        """
        Initialize TikTok uploader with access token

        Args:
            access_token: TikTok OAuth access token
        """
        self.access_token = access_token
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json; charset=UTF-8'
        }

    def upload_video(self, video_file, title, description='', privacy_level='PUBLIC_TO_EVERYONE',
                     disable_duet=False, disable_comment=False, disable_stitch=False,
                     video_cover_timestamp_ms=1000):
        """
        Upload a video to TikTok

        Args:
            video_file: Path to the video file
            title: Video title/caption (max 2200 characters with hashtags)
            description: Additional description
            privacy_level: Privacy setting ('PUBLIC_TO_EVERYONE', 'MUTUAL_FOLLOW_FRIENDS', 'SELF_ONLY')
            disable_duet: Disable duet
            disable_comment: Disable comments
            disable_stitch: Disable stitch
            video_cover_timestamp_ms: Timestamp for video cover in milliseconds

        Returns:
            Dictionary with publish_id and status on success
            None on failure
        """
        if not os.path.exists(video_file):
            raise FileNotFoundError(f"Video file not found: {video_file}")

        # Combine title and description for caption
        caption = title
        if description:
            caption = f"{title}\n\n{description}"

        # Truncate if too long (TikTok limit is 2200 characters)
        if len(caption) > 2200:
            caption = caption[:2197] + "..."

        try:
            print(f"Uploading video to TikTok: {title}")
            print(f"File: {video_file}")

            # Step 1: Initialize upload
            init_response = self._initialize_upload(caption, privacy_level, disable_duet,
                                                     disable_comment, disable_stitch,
                                                     video_cover_timestamp_ms)

            if not init_response or 'data' not in init_response:
                return {
                    'success': False,
                    'error': 'Failed to initialize TikTok upload',
                    'platform': 'tiktok'
                }

            publish_id = init_response['data']['publish_id']
            upload_url = init_response['data']['upload_url']

            print(f"TikTok upload initialized. Publish ID: {publish_id}")

            # Step 2: Upload video file
            upload_success = self._upload_video_file(video_file, upload_url)

            if not upload_success:
                return {
                    'success': False,
                    'error': 'Failed to upload video file to TikTok',
                    'platform': 'tiktok'
                }

            print(f"Video file uploaded successfully")

            # Step 3: Check status
            status = self._check_upload_status(publish_id)

            print(f"TikTok upload complete! Publish ID: {publish_id}")

            return {
                'success': True,
                'publish_id': publish_id,
                'status': status,
                'platform': 'tiktok'
            }

        except Exception as e:
            error_message = f"Error uploading to TikTok: {str(e)}"
            print(error_message)
            return {
                'success': False,
                'error': error_message,
                'platform': 'tiktok'
            }

    def _initialize_upload(self, caption, privacy_level, disable_duet, disable_comment,
                           disable_stitch, video_cover_timestamp_ms):
        """
        Initialize TikTok video upload

        Returns:
            Response JSON with publish_id and upload_url
        """
        data = {
            'post_info': {
                'title': caption,
                'privacy_level': privacy_level,
                'disable_duet': disable_duet,
                'disable_comment': disable_comment,
                'disable_stitch': disable_stitch,
                'video_cover_timestamp_ms': video_cover_timestamp_ms
            },
            'source_info': {
                'source': 'FILE_UPLOAD',
                'post_mode': 'DIRECT_POST'
            }
        }

        response = requests.post(
            self.POST_VIDEO_INIT_URL,
            headers=self.headers,
            json=data
        )

        if response.status_code != 200:
            print(f"TikTok init error: {response.status_code} - {response.text}")
            return None

        return response.json()

    def _upload_video_file(self, video_file, upload_url):
        """
        Upload video file to TikTok's provided URL

        Args:
            video_file: Path to video file
            upload_url: Upload URL from initialization step

        Returns:
            True on success, False on failure
        """
        try:
            # Read video file
            with open(video_file, 'rb') as f:
                video_data = f.read()

            # Upload with PUT request (TikTok uses PUT for file upload)
            headers = {
                'Content-Type': 'video/mp4',
                'Content-Length': str(len(video_data))
            }

            response = requests.put(
                upload_url,
                headers=headers,
                data=video_data
            )

            if response.status_code in [200, 201]:
                return True
            else:
                print(f"TikTok file upload error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"Error uploading file to TikTok: {e}")
            return False

    def _check_upload_status(self, publish_id, max_wait=60):
        """
        Check the status of a TikTok video upload

        Args:
            publish_id: The publish ID from initialization
            max_wait: Maximum seconds to wait for processing

        Returns:
            Status string
        """
        data = {
            'publish_id': publish_id
        }

        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                response = requests.post(
                    self.QUERY_VIDEO_STATUS_URL,
                    headers=self.headers,
                    json=data
                )

                if response.status_code == 200:
                    result = response.json()
                    if 'data' in result:
                        status = result['data'].get('status', 'UNKNOWN')
                        print(f"Upload status: {status}")

                        if status in ['PUBLISH_COMPLETE', 'PROCESSING_DOWNLOAD']:
                            return status

                # Wait before checking again
                time.sleep(5)

            except Exception as e:
                print(f"Error checking status: {e}")
                break

        return 'TIMEOUT'

    def get_video_info(self, publish_id):
        """
        Get information about an uploaded video

        Args:
            publish_id: TikTok publish ID

        Returns:
            Dictionary with video information
        """
        data = {
            'publish_id': publish_id
        }

        try:
            response = requests.post(
                self.QUERY_VIDEO_STATUS_URL,
                headers=self.headers,
                json=data
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting video info: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"Error getting video info: {e}")
            return None
