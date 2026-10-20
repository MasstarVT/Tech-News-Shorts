"""YouTube Shorts via YouTube Data API v3 (videos.insert, resumable upload). Ported from Clip Creator.

Setup (once):
  1. Google Cloud console -> new project -> enable "YouTube Data API v3".
  2. OAuth consent screen: External, add yourself as a test user, then **Publish app**
     ("In production") - in Testing mode refresh tokens expire after 7 days.
  3. Credentials -> OAuth client ID -> Desktop app -> download JSON to
     ``config/secrets/youtube_client_secret.json``.
  4. ``technews auth youtube`` (opens a browser to sign in).

Projects that haven't passed Google's API audit can only upload private videos.
Vertical videos up to 3 minutes are classified as Shorts automatically.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from ..config import load_config
from .base import (
    PostRequest,
    PostResult,
    Publisher,
    PublishError,
    RetryLater,
    client_secret_path,
    load_token,
    save_token,
)

log = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]


def _credentials(account_id: str):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    data = load_token("youtube", account_id)
    if not data:
        raise PublishError(f"YouTube account '{account_id}' is not connected - run `technews auth youtube --account {account_id}`")
    creds = Credentials.from_authorized_user_info(data, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                raise PublishError(f"YouTube token refresh failed ({e}); re-run `technews auth youtube`") from e
            save_token("youtube", account_id, {**data, **json.loads(creds.to_json())})
        else:
            raise PublishError("YouTube credentials invalid; re-run `technews auth youtube`")
    return creds


def authorize(account_id: str) -> dict:
    """Run the installed-app OAuth flow in the browser and store the token."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    secret = client_secret_path("youtube")
    if not secret.exists():
        raise PublishError(f"Missing {secret} - download the OAuth Desktop client JSON from Google Cloud")
    flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    save_token("youtube", account_id, json.loads(creds.to_json()))
    return channel_info(account_id)


def channel_info(account_id: str) -> dict:
    from googleapiclient.discovery import build

    yt = build("youtube", "v3", credentials=_credentials(account_id), cache_discovery=False)
    items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
    if not items:
        return {}
    return {"id": items[0]["id"], "title": items[0]["snippet"]["title"]}


def upload_body(req: PostRequest) -> dict:
    cfg = load_config()
    tags = [t.lstrip("#") for t in req.hashtags][:15]
    description = req.description
    tag_line = " ".join(f"#{t}" for t in tags[:5])
    if "#shorts" not in f"{description} {tag_line}".lower():
        tag_line = (tag_line + " #Shorts").strip()
    return {
        "snippet": {
            "title": req.title[:100],
            "description": f"{description}\n\n{tag_line}".strip()[:5000],
            "tags": tags,
            "categoryId": cfg.publish.youtube_category_id,
        },
        "status": {
            "privacyStatus": req.privacy if req.privacy in ("public", "unlisted", "private") else "private",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": cfg.publish.youtube_synthetic_media,
        },
    }


class YouTubePublisher(Publisher):
    platform = "youtube"

    def publish(self, req: PostRequest) -> PostResult:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError, ResumableUploadError
        from googleapiclient.http import MediaFileUpload

        yt = build("youtube", "v3", credentials=_credentials(self.account_id), cache_discovery=False)
        media = MediaFileUpload(str(req.video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
        insert = yt.videos().insert(part="snippet,status", body=upload_body(req), media_body=media)
        response = None
        try:
            while response is None:
                status, response = insert.next_chunk(num_retries=3)
                if status:
                    log.info("YouTube upload %d%%", int(status.progress() * 100))
        except (HttpError, ResumableUploadError) as e:
            msg = str(e)
            if "quotaExceeded" in msg or "rateLimitExceeded" in msg or "uploadLimitExceeded" in msg:
                raise RetryLater(f"YouTube quota/rate limit: {msg[:300]}") from e
            if getattr(getattr(e, "resp", None), "status", 500) >= 500:
                raise RetryLater(f"YouTube server error: {msg[:300]}") from e
            raise PublishError(f"YouTube rejected the upload: {msg[:500]}") from e
        vid = response["id"]
        privacy = response.get("status", {}).get("privacyStatus", "")
        if req.privacy == "public" and privacy and privacy != "public":
            log.warning("YouTube set video %s to %s (unverified API projects are restricted to private)", vid, privacy)
        return PostResult(remote_id=vid, url=f"https://youtube.com/shorts/{vid}", status="published",
                          state={"uploaded_at": datetime.now(UTC).isoformat(), "privacy": privacy})
