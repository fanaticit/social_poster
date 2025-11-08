# YouTube API Authentication and Video Upload Implementation Guide

YouTube video uploads from desktop applications require OAuth 2.0 authentication with carefully managed tokens and precise API requests. **The YouTube Data API v3 uses the standard `videos.insert` endpoint with resumable uploads supporting files up to 256GB**, requiring 1,600 quota units per upload from the default 10,000 daily allocation. Authentication relies on the installed app OAuth flow with PKCE security, refresh tokens for long-term access, and the `https://www.googleapis.com/auth/youtube.upload` scope as the minimum permission needed.

This implementation guide provides complete technical specifications from official Google documentation, including exact endpoints, required parameters, authentication headers, token lifecycle management, and practical error handling. The OAuth flow opens the system browser for user consent and captures authorization codes via local loopback servers, exchanging them for access tokens (valid ~1 hour) and refresh tokens (valid until revoked). **Videos uploaded from unverified API projects created after July 28, 2020 default to private visibility until the project completes YouTube's compliance audit**—a critical constraint for production applications.

## OAuth 2.0 authentication flow for desktop applications

Desktop applications implement the "installed app" OAuth 2.0 flow, opening the system browser for authorization rather than embedding web views. **This flow requires PKCE (Proof Key for Code Exchange) for enhanced security** and treats desktop apps as public clients unable to securely store secrets, though a client_secret is still provided and used.

The authorization process begins by generating a high-entropy code verifier (43-128 characters using `[A-Z][a-z][0-9]-.~_`) and computing its SHA256 hash as the code challenge. The application then constructs an authorization URL at `https://accounts.google.com/o/oauth2/v2/auth` with required parameters: `client_id`, `redirect_uri` (typically `http://127.0.0.1:PORT` for loopback), `response_type=code`, `scope`, `code_challenge`, `code_challenge_method=S256`, and crucially `access_type=offline` to receive a refresh token.

**The `access_type=offline` parameter is critical**—without it, Google returns no refresh token, forcing full re-authentication when access tokens expire. The state parameter should contain a cryptographically random string (16+ bytes) stored in session before redirect to prevent CSRF attacks, verified when Google redirects back.

After user consent, Google redirects to the specified URI with an authorization code in the `code` parameter or an error in the `error` parameter (such as `access_denied` if the user declines). The application exchanges this code for tokens by POSTing to `https://oauth2.googleapis.com/token` with parameters:

```http
POST /token HTTP/1.1
Host: oauth2.googleapis.com
Content-Type: application/x-www-form-urlencoded

code=4/P7q7W91a-oMsCeLvIaQm6bTrgtp7&
client_id=YOUR_CLIENT_ID&
client_secret=YOUR_CLIENT_SECRET&
redirect_uri=http://127.0.0.1:9004&
grant_type=authorization_code&
code_verifier=YOUR_CODE_VERIFIER
```

The successful response contains an `access_token` (valid ~3920 seconds or 65 minutes), `refresh_token` (always included for installed apps with offline access), `expires_in` (seconds until expiration), `token_type` (always "Bearer"), and `scope` (granted permissions). **The refresh_token enables long-term API access without user interaction**—store it securely as it's the key to maintaining persistent access.

## Secure token storage and refresh procedures

Access tokens expire after approximately one hour, requiring either refresh or full re-authentication. **Refresh tokens should be stored long-term and reused**—Google limits the number issued per client/user combination, and requesting too many causes older ones to stop working. Never store tokens in plain text files, application logs, version control, or (for web apps) browser localStorage.

Platform-specific secure storage is mandatory: **Windows Credential Manager** (Credential Locker), **macOS Keychain Services**, or **Linux Secret Service API** (libsecret). Encrypt tokens before storage even in these secure systems, set restrictive file permissions (read/write only for the application user), and never log token values to console or files. For the client_secret.json configuration file, similar protections apply—don't include it in public repositories and consider additional encryption.

To refresh an access token, POST to `https://oauth2.googleapis.com/token` with parameters:

```http
POST /token HTTP/1.1
Host: oauth2.googleapis.com
Content-Type: application/x-www-form-urlencoded

client_id=YOUR_CLIENT_ID&
client_secret=YOUR_CLIENT_SECRET&
refresh_token=1//xEoDL4iW3cxlI7yDbSRFYNG01kVKM2C-259HOF2aQbI&
grant_type=refresh_token
```

The response contains a new `access_token` and `expires_in` but **does not return a new refresh_token**—reuse the original. Refresh proactively 5 minutes before expiration rather than waiting for 401 errors. Implement token lifecycle management that checks expiration before each API call:

```python
def get_valid_access_token():
    if access_token_exists() and not is_expired():
        return access_token
    elif refresh_token_exists():
        try:
            new_access_token = refresh_access_token()
            save_access_token(new_access_token)
            return new_access_token
        except InvalidGrantError:
            return request_new_authorization()
    else:
        return request_new_authorization()
```

Store token metadata including `expires_at` (current timestamp + expires_in) to enable expiration checking without parsing the token. When refresh fails with `invalid_grant` error (400 status), the refresh token has expired or been revoked—clear stored tokens and initiate full re-authentication.

## YouTube Data API video upload endpoints and procedures

Video uploads use the resumable upload protocol at `https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable` with a two-phase process: first initiating an upload session, then uploading the video file. **Resumable uploads are required for files larger than 5MB** and recommended for all uploads as they support network interruption recovery.

**Phase 1: Initiate resumable session**

POST to the upload endpoint with video metadata and upload information headers:

```http
POST /upload/youtube/v3/videos?uploadType=resumable&part=snippet,status HTTP/1.1
Host: www.googleapis.com
Authorization: Bearer [ACCESS_TOKEN]
Content-Length: [METADATA_BYTE_SIZE]
Content-Type: application/json; charset=UTF-8
X-Upload-Content-Length: [VIDEO_FILE_SIZE_IN_BYTES]
X-Upload-Content-Type: video/*

{
  "snippet": {
    "title": "My video title",
    "description": "Video description",
    "tags": ["tag1", "tag2"],
    "categoryId": "22",
    "defaultLanguage": "en"
  },
  "status": {
    "privacyStatus": "private",
    "embeddable": true,
    "license": "youtube",
    "selfDeclaredMadeForKids": false
  }
}
```

The `part` parameter specifies which resource properties to set—typically `snippet,status` at minimum. **Title must be 1-100 characters** and cannot contain `<` or `>` characters. **Description can be 0-5000 bytes** (not characters—UTF-8 multibyte characters count multiple bytes). **Tags total cannot exceed 500 characters** calculated as `tag1.length + tag2.length + ... + numberOfTags`, though tags 28+ characters don't count toward this limit. CategoryId "22" (People & Blogs) is default; retrieve valid IDs for your region via `GET https://www.googleapis.com/youtube/v3/videoCategories?part=snippet&regionCode=US`.

The response (200 OK) contains a `Location` header with the resumable session URI—save this value as it's needed for all subsequent upload requests. Session URIs expire after some time (not officially documented, but typically hours), requiring restart if expired.

**Phase 2: Upload video file**

PUT the video file to the session URI:

```http
PUT [RESUMABLE_SESSION_URI] HTTP/1.1
Authorization: Bearer [ACCESS_TOKEN]
Content-Length: [VIDEO_FILE_SIZE]
Content-Type: video/*

[BINARY_VIDEO_DATA]
```

For chunked uploads (recommended for large files), include a Content-Range header:

```http
Content-Range: bytes [START_BYTE]-[END_BYTE]/[TOTAL_FILE_SIZE]
```

**Chunk size must be a multiple of 256KB (262,144 bytes)** except for the final chunk. All chunks except the last must be the same size. Example for first chunk of a 3MB file: `Content-Range: bytes 0-524287/3000000`.

When upload completes successfully, the API returns 201 Created with the video resource:

```json
{
  "kind": "youtube#video",
  "id": "VIDEO_ID",
  "snippet": {
    "publishedAt": "2024-01-15T10:30:00.000Z",
    "channelId": "CHANNEL_ID",
    "title": "My video title"
  },
  "status": {
    "uploadStatus": "uploaded",
    "privacyStatus": "private"
  }
}
```

The `uploadStatus` field shows processing state: **"uploaded"** means processing started, **"processed"** means ready for viewing, **"failed"** indicates processing failure, and **"rejected"** means policy violation. Poll the `videos.list` endpoint with the video ID to check processing completion.

If upload is interrupted, check status with an empty PUT request:

```http
PUT [RESUMABLE_SESSION_URI] HTTP/1.1
Authorization: Bearer [ACCESS_TOKEN]
Content-Length: 0
Content-Range: bytes */[TOTAL_FILE_SIZE]
```

The response (308 Resume Incomplete) includes a `Range` header showing successfully uploaded bytes (e.g., `Range: bytes=0-999999`). Resume by uploading remaining data starting from the next byte.

## YouTube Shorts upload requirements and API integration

**YouTube has no dedicated Shorts API or endpoint**—Shorts are uploaded via the standard `videos.insert` endpoint and automatically classified based on technical criteria. YouTube determines a video is a Short when it meets: **duration ≤60 seconds** (recently extended to 3 minutes but 60 seconds recommended), **vertical 9:16 aspect ratio** (specifically 1080x1920 pixels), and preferably the **#Shorts hashtag** in title or description.

Upload Shorts using identical API calls to regular videos, but include the #Shorts hashtag:

```json
{
  "snippet": {
    "title": "My Awesome Short #Shorts",
    "description": "Check out this short video! #Shorts",
    "tags": ["shorts", "youtubeshorts"],
    "categoryId": "10"
  },
  "status": {
    "privacyStatus": "public"
  }
}
```

The categoryId "10" is mentioned in third-party documentation as potentially indicating Shorts, though not officially confirmed by YouTube. **Place #Shorts at the end of the title** for best practices. The hashtag is not strictly required—YouTube's backend classifies based on duration and aspect ratio—but including it improves discoverability and signals intent.

Custom thumbnails for Shorts (if uploaded) should be 9:16 aspect ratio at 1080x1920 pixels, though **thumbnails don't appear in the Shorts feed player**—they only show in the Shorts section on channel pages. Phone verification is required to upload custom thumbnails.

**No API parameter directly designates a video as a Short**—classification happens server-side after processing. To verify a video was classified as a Short, use the YouTube Analytics API with the `creatorContentType` dimension:

```
GET https://youtubeanalytics.googleapis.com/v2/reports?
  ids=channel==MINE&
  dimensions=video,creatorContentType&
  metrics=views&
  startDate=2019-01-01&
  endDate=2024-12-31
```

The `creatorContentType` dimension returns "SHORTS" for short-form vertical videos, "VIDEO_ON_DEMAND" for regular videos, or "LIVE_STREAM" for live content. This dimension only works for videos uploaded after January 1, 2019 and requires the `https://www.googleapis.com/auth/yt-analytics.readonly` scope.

Shorts have identical quota costs (1,600 units) and file size limits (256GB maximum) as regular videos, though practical Shorts file sizes are typically under 10MB given their short duration.

## Rate limits, quota costs, and capacity planning

YouTube Data API uses a quota system allocating **10,000 units per day by default** for development and testing. **Video uploads consume 1,600 units each**, limiting unverified projects to approximately **6 uploads per day** (10,000 ÷ 1,600 = 6.25). Other operations cost significantly less: read operations (list) cost 1 unit, write operations (insert, update) cost 50 units, search requests cost 100 units.

Quotas reset daily at midnight Pacific Time (PT). **Exceeding quota returns a 403 Forbidden error** with `quotaExceeded` reason—there's no automatic overage, and the hard limit is strictly enforced. Production applications require quota increase through YouTube's API compliance audit at https://support.google.com/youtube/contact/yt_api_form.

Additional rate limits exist but are far more generous: **1,800,000 queries per minute per project** and **180,000 queries per minute per user**. These limits rarely impact typical applications, but the daily quota constraint is the primary bottleneck for upload-heavy workflows.

Monitor quota usage in the Google Cloud Console at https://console.cloud.google.com/iam-admin/quotas. Implement client-side quota tracking to warn users when approaching limits (e.g., at 80% consumption). Calculate remaining uploads as: `(remainingQuota / 1600)`. Consider queuing uploads for the next day when quota is exhausted rather than failing.

**File size is limited to 256GB per video** with no official minimum (though practically a few kilobytes). Accepted MIME types include any `video/*` type or `application/octet-stream`. Recommended specifications: **MP4 container, H.264 video codec, AAC-LC audio codec**, with frame rates of 24, 25, 30, 48, 50, or 60 fps. Higher bitrates produce better quality but increase upload time and processing duration.

Video processing time after successful upload typically ranges from 1-30 minutes depending on file size, resolution, and YouTube server load. Processing happens asynchronously—the upload API returns immediately with `uploadStatus: "uploaded"`, and applications should poll periodically to detect when status changes to `"processed"`.

## Error handling for authentication and API failures

OAuth and API errors fall into three categories: authorization endpoint errors during user consent, token exchange/refresh errors, and API request errors during video operations. **Implement different retry strategies for each category**—some errors are transient and retriable, others are permanent failures requiring user action.

**Authorization endpoint errors** appear as query parameters in the redirect URI:

- **`access_denied`**: User declined authorization—handle gracefully by informing user upload features are unavailable
- **`admin_policy_enforced`**: Google Workspace admin restricts scope access—instruct user to contact IT administrator
- **`disallowed_useragent`**: Authorization attempted in embedded WebView—must use system browser
- **`org_internal`**: OAuth client restricted to specific Google Cloud Organization—verify audience settings in consent screen configuration
- **`invalid_grant`**: Code challenge invalid or authorization code expired—regenerate and retry
- **`redirect_uri_mismatch`**: Redirect URI doesn't match Cloud Console configuration—verify exact match including protocol, host, and port

**Token exchange and refresh errors** return JSON with HTTP status codes:

- **400 Bad Request + `invalid_grant`**: Refresh token expired, revoked, or invalid—clear stored tokens and initiate full re-authentication
- **401 Unauthorized + `invalid_client`**: Client authentication failed—verify client_id and client_secret are correct and haven't been regenerated
- **400 Bad Request + `unauthorized_client`**: Client not authorized for grant type—check OAuth client type in Cloud Console

**API request errors** during upload operations:

- **401 Unauthorized + `authError`**: Access token invalid or expired—refresh access token and retry once
- **403 Forbidden + `quotaExceeded`**: Daily quota limit exceeded—stop uploads until midnight PT, display quota exhausted message
- **403 Forbidden + `forbidden`**: Insufficient permissions—verify granted scopes include `youtube.upload`
- **400 Bad Request + `invalidTitle`**: Title violates constraints (empty, too long, or contains `<>`)—validate and correct
- **400 Bad Request + `mediaBodyRequired`**: No video content in request—ensure video file is properly attached
- **404 Not Found**: Resumable session URI expired—restart upload from phase 1
- **500-504 Server Errors**: YouTube server issues—implement exponential backoff (wait 2^retry seconds) and retry up to 5 times

Implement comprehensive error handling with automatic token refresh:

```python
def make_api_request(url, access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 401:
        try:
            new_token = refresh_access_token()
            return make_api_request(url, new_token)
        except RefreshError:
            return initiate_full_reauth()
    
    elif response.status_code == 403:
        error_reason = response.json()["error"]["errors"][0]["reason"]
        if error_reason == "quotaExceeded":
            return handle_quota_exceeded()
        else:
            return handle_permission_error()
    
    elif 500 <= response.status_code < 600:
        return retry_with_backoff()
    
    return response
```

**Never log token values** when recording errors—log only error types, status codes, and sanitized messages. For production applications, implement Cross-Account Protection Service to receive security event notifications (sessions-revoked, tokens-revoked, account-disabled) and take appropriate action.

## OAuth scopes required for video upload

The YouTube Data API defines several OAuth scopes with different permission levels. **For upload-only applications, use `https://www.googleapis.com/auth/youtube.upload`**—this scope grants permission to upload files to the authenticated user's YouTube channel but doesn't allow reading, modifying, or deleting existing videos.

Alternative scopes provide broader access:

- **`https://www.googleapis.com/auth/youtube`**: Full access to manage YouTube account including reading, writing, and deleting videos, playlists, subscriptions
- **`https://www.googleapis.com/auth/youtube.force-ssl`**: Same as above but explicitly requires SSL (functionally identical in practice)
- **`https://www.googleapis.com/auth/youtube.readonly`**: Read-only access to view YouTube account data
- **`https://www.googleapis.com/auth/youtubepartner`**: Partner access for Content ID API (YouTube partners only)

**Follow the principle of least privilege**—request only the minimum scopes your application needs. Users are more likely to grant consent when fewer permissions are requested. Multiple scopes can be requested as a space-delimited list in the authorization URL:

```
scope=https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly
```

URL-encode the space as `%20` or `+` in the final authorization URL. The token exchange response includes a `scope` field showing which permissions were actually granted—**users may deny some scopes** through granular consent, so verify granted scopes:

```python
if "youtube.upload" in response["scope"]:
    enable_upload_functionality()
else:
    show_permission_required_message()
```

**Incremental authorization is not supported for installed apps**—you must request all needed scopes in the initial authorization flow. If additional scopes are needed later, the entire authorization process must be repeated with the expanded scope list.

For API requests, include the access token in the Authorization header:

```http
Authorization: Bearer [ACCESS_TOKEN]
```

This is the preferred method over query string parameters (`?access_token=...`) which can expose tokens in server logs. All YouTube Data API endpoints support the Authorization header.

## Official documentation and implementation best practices

Google's official documentation emphasizes security-first design patterns for OAuth implementation. **Never embed client secrets in native application code**—while desktop apps receive a client_secret, it can be extracted by determined attackers. Protect the client_secret.json configuration file with restrictive permissions and encryption.

**Use PKCE (S256 method) for all authorization requests**—generate a unique code verifier for every authorization flow and compute its SHA256 hash as the challenge. This prevents authorization code interception attacks even if the redirect URI is compromised. The state parameter provides additional CSRF protection—generate cryptographically random strings (16+ bytes), store before redirect, and verify upon return.

**HTTPS is required** for all OAuth and API endpoints except loopback redirects (127.0.0.1 or [::1]) which are exempt. Redirect URIs must match exactly what's registered in Cloud Console including protocol, host, port, and path. Validation rules prohibit IP addresses (except localhost), require domains on the public suffix list, and disallow wildcards, userinfo components, path traversal, and open redirects.

**Open the system browser** for authorization rather than embedding WebViews—embedded user agents are disallowed and return `disallowed_useragent` errors. For desktop apps, the recommended pattern is listening on a local loopback server (http://127.0.0.1:PORT) where PORT is dynamically selected from available ports. Display a success page when authorization completes with instructions to close the browser.

**Handle token refresh proactively** by checking expiration 5 minutes before access tokens expire rather than waiting for 401 errors. This prevents user-visible failures and maintains seamless API access. Store refresh tokens securely and long-term—they enable persistent access without user interaction and are limited in number (requesting too many invalidates older ones).

**Videos uploaded from unverified API projects** (created after July 28, 2020) are restricted to private viewing mode. To make videos public, the project must undergo YouTube's API compliance audit. Submit verification requests at https://support.google.com/youtube/contact/yt_api_form. Apps using sensitive or restricted scopes also require OAuth app verification, displaying "unverified app" warnings until completed.

For resumable uploads, implement exponential backoff for 5xx server errors (500, 502, 503, 504) by waiting 2^retry seconds (2s, 4s, 8s, 16s, 32s) up to a maximum of 5 attempts. **4xx client errors should not be retried**—they indicate permanent failures requiring request correction. Set chunk size based on connection quality: 10-50MB for stable connections, 1-5MB for unstable, with 256KB minimum.

Google provides official client libraries simplifying OAuth and API integration: **google-api-python-client** (Python), **googleapis** (Node.js), **Google.Apis.YouTube.v3** (.NET), **google-api-java-client** (Java), **google-api-go-client** (Go), **google-api-php-client** (PHP), and **google-api-ruby-client** (Ruby). These libraries handle token refresh, retry logic, and protocol details automatically.

## Conclusion: Building production-ready upload applications

Implementing YouTube video uploads requires careful orchestration of OAuth flows, token lifecycle management, and resumable upload protocols with comprehensive error handling. The 1,600 quota unit cost per upload becomes the primary constraint—unverified projects can upload only 6 videos daily, making quota increase applications essential for production use. Desktop applications must balance security (PKCE, encrypted token storage, system browser authentication) with user experience (proactive token refresh, progress tracking, network interruption recovery).

The lack of a dedicated Shorts API means proper video formatting (9:16 aspect ratio, ≤60 seconds) becomes critical for classification, verified only post-upload through Analytics API queries. Understanding that YouTube's automatic classification operates on technical criteria rather than API flags prevents debugging confusion when Shorts don't appear as expected. For production deployments, completing YouTube's API compliance audit lifts the private-only restriction while OAuth app verification removes unverified warnings, both essential for user-facing applications. The comprehensive error handling and retry logic detailed here—distinguishing transient server errors from permanent authorization failures—ensures robust operation despite network issues and API inconsistencies.