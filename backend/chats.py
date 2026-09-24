# -*- coding: utf-8 -*-
"""Group chat: read and reply to real groups from the platform instead of the
WhatsApp app, through the linked account.

This is conversational messaging, one message typed by one operator, and is
kept separate from campaign despatch. It still goes out from the linked
number, so it still counts against the account's standing with WhatsApp.
A throttle protects against accidental floods, and every message is audited.
"""
import datetime as dt
import time
from collections import deque

from sqlalchemy import select, func, desc

from db import (SessionLocal, DirectChat, Group, GroupMeta, GroupMember,
                WaMessage, utcnow)

# Manual sends: at most one every 2 seconds and 15 a minute, across the
# platform. Generous for a person typing, too tight for a stuck key or script.
MIN_GAP_SECONDS = 2.0
MAX_PER_MINUTE = 15
_recent: deque = deque()


def throttle_check() -> str | None:
    """Returns a reason string if a send must be refused right now."""
    now = time.monotonic()
    while _recent and now - _recent[0] > 60:
        _recent.popleft()
    if _recent and now - _recent[-1] < MIN_GAP_SECONDS:
        return f"Please wait {MIN_GAP_SECONDS:.0f} seconds between messages."
    if len(_recent) >= MAX_PER_MINUTE:
        return f"Limit of {MAX_PER_MINUTE} messages a minute reached. This protects the account."
    return None


def throttle_record():
    _recent.append(time.monotonic())


def _num(jid: str) -> str:
    return (jid or "").split("@")[0].split(":")[0]


def my_role(group_id: int, me_jid: str) -> str | None:
    """member, admin, superadmin, or None when membership cannot be confirmed."""
    me = _num(me_jid)
    if not me:
        return None
    with SessionLocal() as s:
        for gm in s.scalars(select(GroupMember).where(GroupMember.group_id == group_id)):
            if _num(gm.jid) == me:
                return gm.role
    return None


def can_send(group_id: int, me_jid: str) -> tuple[bool, str]:
    with SessionLocal() as s:
        meta = s.get(GroupMeta, group_id)
    role = my_role(group_id, me_jid)
    if meta and meta.announce and role not in ("admin", "superadmin"):
        return False, "Only admins can send messages in this group."
    return True, ""


def _preview(last) -> str:
    if last is None:
        return ""
    who = "You" if last.from_me else (last.sender_name or "Them")
    body = last.text or f"[{last.mtype or 'message'}]"
    return f"{who}: {body}"[:90]


def direct_list() -> list[dict]:
    """One to one conversations the platform has opened, plus any it has
    already messaged. Personal chats of the linked account are not included."""
    out, seen = [], set()
    since = utcnow() - dt.timedelta(hours=24)
    with SessionLocal() as s:
        rows = {d.jid: d for d in s.scalars(select(DirectChat))}
        # conversations messaged before direct chats were recorded
        for jid, name, number in s.execute(
                select(WaMessage.chat_jid, func.max(WaMessage.peer_name), func.max(WaMessage.peer_number))
                .where(WaMessage.chat_type == "individual")
                .group_by(WaMessage.chat_jid)).all():
            if jid not in rows:
                rows[jid] = DirectChat(jid=jid, name=name or "", number=number or jid.split("@")[0])
        for jid, d in rows.items():
            if jid in seen:
                continue
            seen.add(jid)
            last = s.scalar(select(WaMessage).where(WaMessage.chat_jid == jid)
                            .order_by(desc(WaMessage.ts)).limit(1))
            today = s.scalar(select(func.count()).select_from(WaMessage).where(
                WaMessage.chat_jid == jid, WaMessage.ts >= since)) or 0
            number = d.number or jid.split("@")[0]
            out.append({
                "key": "d:" + jid, "kind": "direct", "jid": jid, "number": number,
                "name": d.name or _pretty(number), "subtitle": _pretty(number),
                "last_ts": last.ts.isoformat() if last else None,
                "preview": _preview(last), "messages_24h": today,
                "admins_only": False, "can_send": True,
            })
    return out


def _pretty(number: str) -> str:
    from messaging import pretty_number
    return pretty_number(number)


def chat_list(me_jid: str, kind: str = "") -> list[dict]:
    """Every conversation the platform can open: live groups and one to one
    chats, most recently active first."""
    out = []
    with SessionLocal() as s:
        groups = [] if kind == "direct" else list(
            s.scalars(select(Group).where(Group.source == "linked_device")))
        since = utcnow() - dt.timedelta(hours=24)
        for g in groups:
            last = s.scalar(select(WaMessage).where(WaMessage.group_id == g.id)
                            .order_by(desc(WaMessage.ts)).limit(1))
            today = s.scalar(select(func.count()).select_from(WaMessage).where(
                WaMessage.group_id == g.id, WaMessage.ts >= since)) or 0
            meta = s.get(GroupMeta, g.id)
            out.append({
                "key": "g:" + str(g.id), "kind": "group", "group_id": g.id,
                "jid": g.wa_group_id, "name": g.name, "members": g.member_count,
                "subtitle": f"{g.member_count} members",
                "last_ts": last.ts.isoformat() if last else None,
                "preview": _preview(last), "messages_24h": today,
                "admins_only": bool(meta and meta.announce),
            })
    for item in out:
        ok, _ = can_send(item["group_id"], me_jid)
        item["can_send"] = ok
    if kind != "group":
        out += direct_list()
    out.sort(key=lambda x: x["last_ts"] or "", reverse=True)
    return out


def open_direct(number: str, name: str = "") -> dict:
    """Record a one to one conversation so it appears in the chat list and
    that person's replies are stored. Sends nothing."""
    jid = f"{number}@s.whatsapp.net"
    with SessionLocal() as s:
        d = s.get(DirectChat, jid)
        if d is None:
            d = DirectChat(jid=jid, number=number, name=name[:160])
            s.add(d)
        elif name:
            d.name = name[:160]
        s.commit()
        out = {"key": "d:" + jid, "kind": "direct", "jid": jid, "number": number,
               "name": d.name or _pretty(number), "subtitle": _pretty(number),
               "can_send": True, "admins_only": False}
    return out


def resolve(key: str) -> dict | None:
    """Turn a chat key into what the send path and thread view need."""
    if not key or ":" not in key:
        return None
    kind, ident = key.split(":", 1)
    with SessionLocal() as s:
        if kind == "g":
            g = s.get(Group, int(ident)) if ident.isdigit() else None
            if g is None:
                return None
            return {"kind": "group", "group_id": g.id, "jid": g.wa_group_id, "name": g.name,
                    "subtitle": f"{g.member_count} members"}
        if kind == "d":
            d = s.get(DirectChat, ident)
            number = (d.number if d else ident.split("@")[0])
            name = (d.name if d and d.name else "")
            if d is None:
                m = s.scalar(select(WaMessage).where(WaMessage.chat_jid == ident)
                             .order_by(desc(WaMessage.ts)).limit(1))
                if m is None:
                    return None
                name = m.peer_name or ""
                number = m.peer_number or number
            return {"kind": "direct", "jid": ident, "number": number, "raw_name": name,
                    "name": name or _pretty(number), "subtitle": _pretty(number)}
    return None
