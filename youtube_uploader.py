"""
YouTube Uploader - Handles video uploads to YouTube
Supports Shorts and regular videos with full metadata
"""

import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import time


class YouTubeUploader:
    """Handles uploading videos to YouTube"""

    def __init__(self, credentials):
        """
        Initialize YouTube uploader with credentials

        Args:
            credentials: Google OAuth2 credentials object
        """
        self.youtube = build('youtube', 'v3', credentials=credentials)

    def upload_video(self, video_file, title, description, tags, category_id='20',
                     privacy_status='public', made_for_kids=False):
        """
        Upload a video to YouTube

        Args:
            video_file: Path to the video file
            title: Video title (max 100 characters)
            description: Video description
            tags: List of tags
            category_id: YouTube category ID (default '20' for Gaming)
            privacy_status: 'public', 'private', or 'unlisted'
            made_for_kids: Whether the video is made for kids

        Returns:
            Dictionary with video_id and video_url on success
            None on failure
        """
        if not os.path.exists(video_file):
            raise FileNotFoundError(f"Video file not found: {video_file}")

        # Prepare video metadata
        body = {
            'snippet': {
                'title': title[:100],  # YouTube title limit
                'description': description,
                'tags': tags[:500],  # YouTube allows up to 500 tags
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': privacy_status.lower(),
                'selfDeclaredMadeForKids': made_for_kids
            }
        }

        # Create media file upload
        media = MediaFileUpload(
            video_file,
            chunksize=-1,  # Upload in a single request
            resumable=True,
            mimetype='video/*'
        )

        try:
            print(f"Uploading video to YouTube: {title}")
            print(f"File: {video_file}")

            # Execute the upload
            request = self.youtube.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"Upload progress: {progress}%")

            video_id = response['id']
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            print(f"Upload complete! Video ID: {video_id}")
            print(f"Video URL: {video_url}")

            return {
                'success': True,
                'video_id': video_id,
                'video_url': video_url,
                'platform': 'youtube'
            }

        except HttpError as e:
            error_message = f"YouTube API error: {e}"
            print(f"Error uploading to YouTube: {error_message}")
            return {
                'success': False,
                'error': error_message,
                'platform': 'youtube'
            }
        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            print(f"Error uploading to YouTube: {error_message}")
            return {
                'success': False,
                'error': error_message,
                'platform': 'youtube'
            }

    def get_video_info(self, video_id):
        """
        Get information about an uploaded video

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with video information
        """
        try:
            request = self.youtube.videos().list(
                part='snippet,status,statistics',
                id=video_id
            )
            response = request.execute()

            if response['items']:
                return response['items'][0]
            else:
                return None

        except HttpError as e:
            print(f"Error getting video info: {e}")
            return None

    def update_video(self, video_id, title=None, description=None, tags=None,
                     privacy_status=None):
        """
        Update video metadata

        Args:
            video_id: YouTube video ID
            title: New title (optional)
            description: New description (optional)
            tags: New tags list (optional)
            privacy_status: New privacy status (optional)

        Returns:
            True on success, False on failure
        """
        try:
            # Get current video details
            video = self.get_video_info(video_id)
            if not video:
                return False

            body = {'id': video_id}

            # Update snippet if any snippet fields are provided
            if title or description or tags:
                body['snippet'] = video['snippet']
                if title:
                    body['snippet']['title'] = title[:100]
                if description:
                    body['snippet']['description'] = description
                if tags:
                    body['snippet']['tags'] = tags[:500]

            # Update status if privacy is provided
            if privacy_status:
                body['status'] = video['status']
                body['status']['privacyStatus'] = privacy_status.lower()

            # Determine which parts to update
            parts = []
            if 'snippet' in body:
                parts.append('snippet')
            if 'status' in body:
                parts.append('status')

            if not parts:
                return True  # Nothing to update

            request = self.youtube.videos().update(
                part=','.join(parts),
                body=body
            )
            response = request.execute()

            print(f"Video {video_id} updated successfully")
            return True

        except HttpError as e:
            print(f"Error updating video: {e}")
            return False

    def delete_video(self, video_id):
        """
        Delete a video from YouTube

        Args:
            video_id: YouTube video ID

        Returns:
            True on success, False on failure
        """
        try:
            self.youtube.videos().delete(id=video_id).execute()
            print(f"Video {video_id} deleted successfully")
            return True
        except HttpError as e:
            print(f"Error deleting video: {e}")
            return False
