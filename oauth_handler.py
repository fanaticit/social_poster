"""
OAuth Handler - Manages authentication for YouTube and TikTok
Handles token storage, refresh, and OAuth consent flow
"""

import os
import json
import pickle
import webbrowser
import hashlib
import base64
import secrets
import certifi
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import requests
from oauth_callback_server import start_oauth_server


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
        print("Starting local OAuth callback server...")

        # Use localhost redirect URI
        redirect_uri = 'http://localhost:8000/callback'

        # Generate PKCE code verifier and challenge (required by TikTok)
        # TikTok uses HEX encoding (not Base64-URL) - this is non-standard!
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        # TikTok requires SHA256 hash as HEX string (not Base64-URL encoded)
        code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).hexdigest()

        print(f"DEBUG: Code verifier length: {len(code_verifier)}")
        print(f"DEBUG: Code verifier: {code_verifier}")
        print(f"DEBUG: Code challenge length: {len(code_challenge)}")
        print(f"DEBUG: Code challenge (HEX): {code_challenge}")

        # Store code_verifier for later use in token exchange
        self._pkce_code_verifier = code_verifier

        # Build authorization URL with PKCE
        # Include both user.info.basic and video.publish scopes (for Content Posting API)
        auth_params = {
            'client_key': client_key,
            'scope': 'user.info.basic,video.publish',
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }

        auth_url = self.TIKTOK_AUTH_URL + '?' + '&'.join([f"{k}={v}" for k, v in auth_params.items()])

        print(f"\nOpening browser for TikTok authorization...")

        # Try to open in Chrome specifically on macOS
        try:
            chrome_path = r'open -a /Applications/Google\ Chrome.app %s'
            webbrowser.get(chrome_path).open(auth_url)
        except:
            # Fallback to default browser
            webbrowser.open(auth_url)

        # Start local server to receive callback
        auth_code = start_oauth_server(port=8000, timeout=300)

        if not auth_code:
            raise Exception("Failed to get authorization code from TikTok")

        # Exchange code for access token (with code_verifier for PKCE)
        token_data = self._exchange_tiktok_code(auth_code, client_key, client_secret, redirect_uri, code_verifier)

        # Save token
        with open(token_path, 'w') as f:
            json.dump(token_data, f, indent=2)

        print(f"TikTok credentials saved for {account_name}")
        return token_data

    def _exchange_tiktok_code(self, code, client_key, client_secret, redirect_uri, code_verifier=None):
        """
        Exchange TikTok authorization code for access token

        Args:
            code: Authorization code from OAuth callback
            client_key: TikTok app client key
            client_secret: TikTok app client secret
            redirect_uri: Redirect URI used in authorization
            code_verifier: PKCE code verifier (required for PKCE flow)

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

        # Add code_verifier for PKCE
        if code_verifier:
            data['code_verifier'] = code_verifier
            print(f"DEBUG: Sending code_verifier of length {len(code_verifier)}")

        print(f"DEBUG: Token exchange data keys: {list(data.keys())}")

        # Temporarily disable SSL verification (TODO: fix certificates properly)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.post(self.TIKTOK_TOKEN_URL, data=data, verify=False)

        if response.status_code != 200:
            print(f"TikTok token exchange error: {response.status_code}")
            print(f"Response: {response.text}")
            raise Exception(f"Failed to get TikTok access token: {response.status_code} - {response.text}")

        result = response.json()

        # Check if the response contains an error
        if 'error' in result:
            error_msg = result.get('error_description', result.get('error'))
            print(f"TikTok API Error: {error_msg}")
            print(f"Full response: {result}")
            raise Exception(f"TikTok API error: {error_msg}")

        print(f"Token exchange successful!")
        return result

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

        # Temporarily disable SSL verification (TODO: fix certificates properly)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.post(self.TIKTOK_TOKEN_URL, data=data, verify=False)

        if response.status_code != 200:
            raise Exception(f"Failed to refresh TikTok token: {response.text}")

        return response.json()
