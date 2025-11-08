"""
TikTok Uploader - Handles video uploads to TikTok
Uses TikTok Content Posting API v2
"""

import os
import requests
import time
import json
import certifi


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

    def upload_video(self, video_file, title, description='', privacy_level='SELF_ONLY',
                     disable_duet=False, disable_comment=False, disable_stitch=False,
                     video_cover_timestamp_ms=1000):
        """
        Upload a video to TikTok

        Args:
            video_file: Path to the video file
            title: Video title/caption (max 2200 characters with hashtags)
            description: Additional description
            privacy_level: Privacy setting ('PUBLIC_TO_EVERYONE', 'MUTUAL_FOLLOW_FRIENDS', 'SELF_ONLY')
                          NOTE: Unaudited/sandbox apps can ONLY use 'SELF_ONLY' (private)
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

            # Warn if using sandbox/private mode
            if privacy_level == 'SELF_ONLY':
                print(f"⚠️  Privacy: SELF_ONLY (Private) - Unaudited apps can only post private videos")

            # Step 1: Get video file size
            video_size = os.path.getsize(video_file)
            print(f"Video size: {video_size} bytes ({video_size / (1024*1024):.2f} MB)")

            # Step 2: Initialize upload (returns chunk info too)
            init_result = self._initialize_upload(caption, privacy_level, disable_duet,
                                                   disable_comment, disable_stitch,
                                                   video_cover_timestamp_ms, video_size)

            if not init_result or not init_result.get('response') or 'data' not in init_result['response']:
                return {
                    'success': False,
                    'error': 'Failed to initialize TikTok upload',
                    'platform': 'tiktok'
                }

            init_response = init_result['response']
            publish_id = init_response['data']['publish_id']
            upload_url = init_response['data']['upload_url']
            chunk_size = init_result['chunk_size']
            total_chunks = init_result['total_chunks']

            print(f"TikTok upload initialized. Publish ID: {publish_id}")

            # Step 3: Upload video file in chunks
            upload_success = self._upload_video_file(
                video_file,
                upload_url,
                chunk_size=chunk_size,
                total_chunks=total_chunks
            )

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
                           disable_stitch, video_cover_timestamp_ms, video_size):
        """
        Initialize TikTok video upload

        Args:
            video_size: Size of video file in bytes

        Returns:
            Response JSON with publish_id and upload_url
        """
        # TikTok chunking rules:
        # - Videos < 5MB must upload as whole (chunk_size = video_size)
        # - Chunk size must be 5-64 MB
        # - total_chunk_count should be calculated using ceiling division

        min_chunk_size = 5 * 1024 * 1024  # 5 MB minimum
        max_chunk_size = 64 * 1024 * 1024  # 64 MB maximum

        if video_size < min_chunk_size:
            # Videos under 5MB upload as whole
            chunk_size = video_size
            total_chunk_count = 1
        else:
            # Use fixed 10 MB chunks
            chunk_size = 10 * 1024 * 1024  # 10 MB
            # Use floor division - TikTok expects this
            # We'll upload remaining bytes in the last chunk
            total_chunk_count = video_size // chunk_size

        # Debug output
        print(f"\n=== TikTok Upload Initialization Debug ===")
        print(f"Video size: {video_size:,} bytes ({video_size / (1024*1024):.2f} MB)")
        print(f"Chunk size: {chunk_size:,} bytes ({chunk_size / (1024*1024):.2f} MB)")
        print(f"Total chunk count: {total_chunk_count}")
        print(f"Calculation: {video_size} / {chunk_size} = {video_size / chunk_size:.4f}")
        print(f"==========================================\n")

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
                'video_size': video_size,
                'chunk_size': chunk_size,
                'total_chunk_count': total_chunk_count
            }
        }

        print(f"Request payload:")
        print(json.dumps(data, indent=2))

        response = requests.post(
            self.POST_VIDEO_INIT_URL,
            headers=self.headers,
            json=data,
            verify=False
        )

        print(f"\nResponse status: {response.status_code}")
        print(f"Response body: {response.text}\n")

        if response.status_code == 429:
            print(f"⚠️  Rate limit exceeded. TikTok requires waiting before next attempt.")
            print(f"   Suggested: Wait 5-10 minutes before retrying.")
            return None
        elif response.status_code == 403:
            error_data = response.json().get('error', {})
            error_code = error_data.get('code', '')

            if error_code == 'unaudited_client_can_only_post_to_private_accounts':
                print(f"❌ TikTok Account Privacy Error:")
                print(f"   Your TikTok app is in sandbox/unaudited mode.")
                print(f"   ")
                print(f"   REQUIRED: Your TikTok account must be set to PRIVATE")
                print(f"   ")
                print(f"   To fix this:")
                print(f"   1. Open TikTok app or website")
                print(f"   2. Go to Settings > Privacy")
                print(f"   3. Change account from Public to Private")
                print(f"   4. Try uploading again")
                print(f"   ")
                print(f"   Note: After TikTok approves your app, you can make your account public again.")
            else:
                print(f"TikTok init error: {response.status_code} - {response.text}")
            return None
        elif response.status_code != 200:
            print(f"TikTok init error: {response.status_code} - {response.text}")
            return None

        return {
            'response': response.json(),
            'chunk_size': chunk_size,
            'total_chunks': total_chunk_count
        }

    def _upload_video_file(self, video_file, upload_url, chunk_size=10485760, total_chunks=11):
        """
        Upload video file to TikTok in chunks

        Args:
            video_file: Path to video file
            upload_url: Upload URL from initialization step
            chunk_size: Size of each chunk in bytes
            total_chunks: Total number of chunks

        Returns:
            True on success, False on failure
        """
        try:
            # Read entire video file
            with open(video_file, 'rb') as f:
                video_data = f.read()

            video_size = len(video_data)
            print(f"Uploading {video_size:,} bytes in {total_chunks} chunks...")

            # Upload file in chunks
            for chunk_index in range(total_chunks):
                start_byte = chunk_index * chunk_size

                # For the last declared chunk, include ALL remaining bytes
                if chunk_index == total_chunks - 1:
                    # This is the last chunk TikTok expects - send everything remaining
                    end_byte = video_size
                else:
                    end_byte = min(start_byte + chunk_size, video_size)

                chunk_data = video_data[start_byte:end_byte]

                # Actual end byte is start + length of chunk data - 1 (for 0-indexed)
                actual_end_byte = start_byte + len(chunk_data) - 1

                # Content-Range header: bytes start-end/total
                content_range = f"bytes {start_byte}-{actual_end_byte}/{video_size}"

                headers = {
                    'Content-Type': 'video/mp4',
                    'Content-Length': str(len(chunk_data)),
                    'Content-Range': content_range
                }

                print(f"  Chunk {chunk_index + 1}/{total_chunks}: {content_range} ({len(chunk_data)} bytes)")

                response = requests.put(
                    upload_url,
                    data=chunk_data,
                    headers=headers,
                    verify=False,
                    timeout=60
                )

                # Check response for each chunk
                # 200 = OK, 201 = Created, 204 = No Content, 206 = Partial Content (chunked upload success)
                if response.status_code not in [200, 201, 204, 206]:
                    print(f"❌ Chunk {chunk_index + 1} upload failed: HTTP {response.status_code}")
                    if response.text and response.text != 'null':
                        print(f"   Response: {response.text}")
                    return False

                print(f"    ✓ Uploaded successfully")

            print(f"✓ All chunks uploaded successfully")
            return True

        except Exception as e:
            print(f"❌ Error uploading file to TikTok: {e}")
            import traceback
            traceback.print_exc()
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
                    json=data,
                    verify=False
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
                json=data,
                verify=False
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting video info: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"Error getting video info: {e}")
            return None
