"""
OAuth Handler - Manages authentication for YouTube and TikTok
Handles token storage, refresh, and OAuth consent flow
"""

import os
import json
import pickle
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import requests


class OAuthHandler:
    """Handles OAuth authentication for multiple platforms and accounts"""

    YOUTUBE_SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    TIKTOK_AUTH_URL = 'https://www.tiktok.com/v2/auth/authorize/'
    TIKTOK_TOKEN_URL = 'https://open.tiktokapis.com/v2/oauth/token/'

    def __init__(self, credentials_dir='credentials'):
        self.credentials_dir = Path(credentials_dir)
        self.credentials_dir.mkdir(parents=True, exist_ok=True)

    def get_youtube_credentials(self, account_name, token_file, credentials_file='credentials/youtube_credentials.json'):
        """
        Get or create YouTube OAuth credentials for a specific account

        Args:
            account_name: Name of the account (e.g., 'english', 'japanese')
            token_file: Path to store the token file
            credentials_file: Path to the OAuth client credentials JSON

        Returns:
            Credentials object for YouTube API
        """
        token_path = Path(token_file)
        token_path.parent.mkdir(parents=True, exist_ok=True)

        creds = None

        # Check if token file exists
        if token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), self.YOUTUBE_SCOPES)
            except Exception as e:
                print(f"Error loading existing token for {account_name}: {e}")

        # If credentials are invalid or don't exist, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    print(f"Refreshing expired token for YouTube {account_name}...")
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    creds = None

            if not creds:
                # Start OAuth flow
                if not Path(credentials_file).exists():
                    raise FileNotFoundError(
                        f"YouTube credentials file not found at {credentials_file}. "
                        f"Please download OAuth credentials from Google Cloud Console."
                    )

                print(f"\nStarting OAuth flow for YouTube {account_name}...")
                print(f"A browser window will open for authentication.")

                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file,
                    self.YOUTUBE_SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save the credentials for future use
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            print(f"Credentials saved for YouTube {account_name}")

        return creds

    def get_tiktok_credentials(self, account_name, token_file, client_key, client_secret):
        """
        Get or create TikTok OAuth credentials for a specific account

        Args:
            account_name: Name of the account (e.g., 'english', 'japanese')
            token_file: Path to store the token file
            client_key: TikTok app client key
            client_secret: TikTok app client secret

        Returns:
            Dictionary with access token and other credentials
        """
        token_path = Path(token_file)
        token_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if token file exists and is valid
        if token_path.exists():
            try:
                with open(token_path, 'r') as f:
                    token_data = json.load(f)

                # Check if token is still valid (simple check)
                if 'access_token' in token_data:
                    # TODO: Add token expiration check
                    print(f"Using existing token for TikTok {account_name}")
                    return token_data
            except Exception as e:
                print(f"Error loading existing TikTok token for {account_name}: {e}")

        # Need to get new token through OAuth flow
        print(f"\nTikTok OAuth flow for {account_name}...")
        print("Note: TikTok OAuth requires a web callback URL.")
        print("Please ensure your TikTok app is configured with a redirect URI.")

        # For TikTok, we need to use authorization code flow
        # This is a simplified version - production would need a proper web server
        redirect_uri = input("Enter your TikTok app redirect URI: ")

        # Build authorization URL
        auth_params = {
            'client_key': client_key,
            'scope': 'video.upload',
            'response_type': 'code',
            'redirect_uri': redirect_uri,
        }

        auth_url = self.TIKTOK_AUTH_URL + '?' + '&'.join([f"{k}={v}" for k, v in auth_params.items()])

        print(f"\nPlease visit this URL to authorize the app:")
        print(auth_url)

        auth_code = input("\nEnter the authorization code from the redirect URL: ")

        # Exchange code for access token
        token_data = self._exchange_tiktok_code(auth_code, client_key, client_secret, redirect_uri)

        # Save token
        with open(token_path, 'w') as f:
            json.dump(token_data, f, indent=2)

        print(f"TikTok credentials saved for {account_name}")
        return token_data

    def _exchange_tiktok_code(self, code, client_key, client_secret, redirect_uri):
        """
        Exchange TikTok authorization code for access token

        Args:
            code: Authorization code from OAuth callback
            client_key: TikTok app client key
            client_secret: TikTok app client secret
            redirect_uri: Redirect URI used in authorization

        Returns:
            Dictionary with access token and refresh token
        """
        data = {
            'client_key': client_key,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
        }

        response = requests.post(self.TIKTOK_TOKEN_URL, data=data)

        if response.status_code != 200:
            raise Exception(f"Failed to get TikTok access token: {response.text}")

        return response.json()

    def refresh_tiktok_token(self, refresh_token, client_key, client_secret):
        """
        Refresh TikTok access token using refresh token

        Args:
            refresh_token: The refresh token
            client_key: TikTok app client key
            client_secret: TikTok app client secret

        Returns:
            Dictionary with new access token
        """
        data = {
            'client_key': client_key,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }

        response = requests.post(self.TIKTOK_TOKEN_URL, data=data)

        if response.status_code != 200:
            raise Exception(f"Failed to refresh TikTok token: {response.text}")

        return response.json()
