# -*- coding: utf-8 -*-
"""Signed tokens for tracked media endpoints.

A tracked link gets a database row because clicks are counted against it. A
tracked media view does not need one: the campaign, group and media ids are
carried in the token itself and signed, so the endpoint can attribute a view
without a lookup table.
"""
import base64
import hashlib
import hmac

from db import SessionLocal, Setting


def _key() -> bytes:
    with SessionLocal() as s:
        row = s.get(Setting, "media_token_key")
        if row is None:
            import secrets
            row = Setting(key="media_token_key", value=secrets.token_hex(32))
            s.add(row)
            s.commit()
        return row.value.encode()


def make_media_token(campaign_id: int, group_id: int, media_id: int) -> str:
    payload = f"{campaign_id}.{group_id}.{media_id}"
    sig = hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()[:10]
    raw = f"{payload}.{sig}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def read_media_token(token: str) -> tuple[int, int, int] | None:
    try:
        pad = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(token + pad).decode()
        cid, gid, mid, sig = raw.split(".")
        payload = f"{cid}.{gid}.{mid}"
        expect = hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()[:10]
        if not hmac.compare_digest(sig, expect):
            return None
        return int(cid), int(gid), int(mid)
    except Exception:
        return None
