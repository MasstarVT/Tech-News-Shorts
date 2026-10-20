"""TikTok via the Content Posting API. Ported from Clip Creator.

Default mode is **inbox draft** (``video.upload`` scope): the video lands in the TikTok app's inbox and you
tap publish. TikTok only lets audited apps post publicly, and its guidelines don't approve tools for posting to
your own accounts, so fully automatic public posting is not offered. ``mode: direct`` (``video.publish``) is
implemented for audited apps; unaudited apps can only post SELF_ONLY (private) that way.

Connect: set TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET / TIKTOK_REDIRECT_URI in .env, then
``technews auth tiktok`` and paste the redirected URL.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import math
import secrets as pysecrets
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from ..config import secret
from .base import PostRequest, PostResult, Publisher, PublishError, RetryLater, load_token, save_token

log = logging.getLogger(__name__)
API = "https://open.tiktokapis.com/v2"
SCOPES = "user.info.basic,video.upload,video.publish"
MB = 1024 * 1024


def _now() -> datetime:
    return datetime.now(UTC)


def _pkce() -> tuple[str, str]:
    verifier = pysecrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def authorize_url(state_store: dict) -> str:
    key, redirect = secret("TIKTOK_CLIENT_KEY"), secret("TIKTOK_REDIRECT_URI")
    if not (key and redirect):
        raise PublishError("Set TIKTOK_CLIENT_KEY and TIKTOK_REDIRECT_URI in .env")
    verifier, challenge = _pkce()
    state = pysecrets.token_urlsafe(16)
    state_store.update({"verifier": verifier, "state": state})
    return "https://www.tiktok.com/v2/auth/authorize/?" + urlencode({
        "client_key": key, "scope": SCOPES, "response_type": "code", "redirect_uri": redirect, "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256"})


def _save(account_id: str, tok: dict) -> dict:
    now = _now()
    data = {
        "access_token": tok["access_token"], "refresh_token": tok.get("refresh_token", ""),
        "open_id": tok.get("open_id", ""), "scope": tok.get("scope", ""),
        "expires_at": (now + timedelta(seconds=int(tok.get("expires_in", 86400)))).isoformat(),
        "refresh_expires_at": (now + timedelta(seconds=int(tok.get("refresh_expires_in", 365 * 86400)))).isoformat(),
    }
    try:
        r = httpx.get(f"{API}/user/info/", params={"fields": "open_id,display_name"},
                      headers={"Authorization": f"Bearer {data['access_token']}"}, timeout=20)
        data["display_name"] = r.json().get("data", {}).get("user", {}).get("display_name", "")
    except Exception:
        data["display_name"] = ""
    save_token("tiktok", account_id, data)
    return data


def authorize_with_redirect(account_id: str, redirected_url: str, state_store: dict) -> dict:
    q = parse_qs(urlparse(redirected_url).query)
    code = q.get("code", [""])[0]
    if not code:
        raise PublishError("No ?code= in the pasted URL")
    if state_store.get("state") and q.get("state", [""])[0] != state_store["state"]:
        raise PublishError("OAuth state mismatch - start the sign-in again")
    r = httpx.post(f"{API}/oauth/token/", data={
        "client_key": secret("TIKTOK_CLIENT_KEY"), "client_secret": secret("TIKTOK_CLIENT_SECRET"), "code": code,
        "grant_type": "authorization_code", "redirect_uri": secret("TIKTOK_REDIRECT_URI"),
        "code_verifier": state_store.get("verifier", "")}, timeout=20)
    tok = r.json()
    if r.status_code != 200 or "access_token" not in tok:
        raise PublishError(f"TikTok token exchange failed: {tok}")
    return _save(account_id, tok)


def refresh(account_id: str, force: bool = False) -> dict | None:
    data = load_token("tiktok", account_id)
    if not data:
        return None
    if not force and datetime.fromisoformat(data["expires_at"]) - _now() > timedelta(minutes=30):
        return data
    r = httpx.post(f"{API}/oauth/token/", data={
        "client_key": secret("TIKTOK_CLIENT_KEY"), "client_secret": secret("TIKTOK_CLIENT_SECRET"),
        "grant_type": "refresh_token", "refresh_token": data["refresh_token"]}, timeout=20)
    tok = r.json()
    if r.status_code != 200 or "access_token" not in tok:
        log.warning("TikTok refresh failed for %s: %s", account_id, tok)
        return None
    return _save(account_id, tok)


def chunk_plan(size: int) -> tuple[int, int]:
    """(chunk_size, total_chunks) following TikTok's rules (5-64 MB chunks, last chunk takes remainder)."""
    if size <= 64 * MB:
        return size, 1
    chunk = 10 * MB
    return chunk, int(math.floor(size / chunk))


class TikTokPublisher(Publisher):
    platform = "tiktok"

    def _headers(self) -> dict[str, str]:
        data = refresh(self.account_id)
        if not data:
            raise PublishError(f"TikTok account '{self.account_id}' is not connected/expired - run "
                               f"`technews auth tiktok --account {self.account_id}`")
        return {"Authorization": f"Bearer {data['access_token']}", "Content-Type": "application/json; charset=UTF-8"}

    def _post(self, path: str, body: dict) -> dict:
        r = httpx.post(f"{API}{path}", json=body, headers=self._headers(), timeout=30)
        d = r.json() if r.content else {}
        err = d.get("error", {})
        if r.status_code == 429 or err.get("code") in ("rate_limit_exceeded", "spam_risk_too_many_pending_share"):
            raise RetryLater(f"TikTok rate limit: {err}")
        if r.status_code != 200 or err.get("code") not in (None, "ok"):
            raise PublishError(f"TikTok {path} failed: {err or r.text[:300]}")
        return d.get("data", {})

    def publish(self, req: PostRequest) -> PostResult:
        size = req.video.stat().st_size
        chunk, total = chunk_plan(size)
        source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": total}
        if req.mode == "direct":
            info = self._post("/post/publish/creator_info/query/", {})
            options = info.get("privacy_level_options", ["SELF_ONLY"])
            privacy = "PUBLIC_TO_EVERYONE" if req.privacy == "public" and "PUBLIC_TO_EVERYONE" in options else "SELF_ONLY"
            title = f"{req.title} {' '.join('#' + t for t in req.hashtags)}"[:2200]
            data = self._post("/post/publish/video/init/", {
                "post_info": {"title": title, "privacy_level": privacy, "disable_duet": False,
                              "disable_comment": False, "disable_stitch": False, "video_cover_timestamp_ms": 1000,
                              "brand_content_toggle": False, "brand_organic_toggle": False,
                              "is_aigc": req.ai_generated},
                "source_info": source})
        else:
            data = self._post("/post/publish/inbox/video/init/", {"source_info": source})
        publish_id, upload_url = data["publish_id"], data["upload_url"]
        with req.video.open("rb") as fh:
            for i in range(total):
                start = i * chunk
                end = size - 1 if i == total - 1 else start + chunk - 1
                fh.seek(start)
                body = fh.read(end - start + 1)
                r = httpx.put(upload_url, content=body, timeout=300, headers={
                    "Content-Range": f"bytes {start}-{end}/{size}", "Content-Length": str(len(body)),
                    "Content-Type": "video/mp4"})
                if r.status_code not in (200, 201, 206):
                    raise RetryLater(f"TikTok chunk {i + 1}/{total} upload failed: {r.status_code} {r.text[:200]}")
        state = {"publish_id": publish_id, "mode": req.mode or "inbox_draft"}
        deadline = time.time() + 300
        while time.time() < deadline:
            res = self.check(state)
            if res:
                return res
            time.sleep(8)
        return PostResult(remote_id=publish_id, status="processing", state=state)

    def check(self, state: dict) -> PostResult | None:
        d = self._post("/post/publish/status/fetch/", {"publish_id": state["publish_id"]})
        st = d.get("status", "")
        if st == "FAILED":
            raise PublishError(f"TikTok processing failed: {d.get('fail_reason', 'unknown')}")
        if st == "SEND_TO_USER_INBOX":
            return PostResult(remote_id=state["publish_id"], status="needs_action", state=state)
        if st == "PUBLISH_COMPLETE":
            ids = d.get("publicaly_available_post_id") or d.get("publicly_available_post_id") or []
            url = f"https://www.tiktok.com/video/{ids[0]}" if ids else ""
            return PostResult(remote_id=str(ids[0]) if ids else state["publish_id"], url=url, status="published",
                              state=state)
        return None
