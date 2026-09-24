# -*- coding: utf-8 -*-
"""Consumes what the linked WhatsApp account observes and stores it locally.

Four streams arrive from the bridge:

  receipts  delivery and read receipts for messages this account sent
  messages  group messages, and one to one messages with numbers the
            platform has messaged, live and from history sync
  reactions emoji reactions, a subset of the message stream
  groups    each group's profile: description, settings, members

Data model
  Message (WaMessage) -> Recipient receipts (WaReceipt, one row per recipient)
  The counters and status on a message are always derived from its receipt
  rows, never incremented, so a duplicated provider event cannot inflate them.

Status rules
  Pending -> Sent -> Delivered -> Read, or Pending/Sent -> Failed.
  Status only moves forward. Acceptance by the send call is Pending: a
  message is Sent only when WhatsApp's server acknowledges it, Delivered and
  Read only when receipts say so.
  Individual message: status follows its one recipient.
  Group message: follows WhatsApp's own tick semantics, Delivered when every
  recipient has it and Read when every recipient has read it; partial
  progress is carried by the counts.

Baileys status values, mapped to the WhatsApp webhook vocabulary:
    0 ERROR -> failed   2 SERVER_ACK -> sent   3 DELIVERY_ACK -> delivered
    4 READ  -> read     5 PLAYED     -> read
"""
import asyncio
import datetime as dt

from sqlalchemy import select, func, delete

import adapters
from db import (SessionLocal, Delivery, DirectChat, Group, GroupMeta, GroupMember,
                Interaction, WaMessage, WaReceipt, WaReaction, utcnow)

RANK = {"queued": 0, "pending": 0, "": 0, "sent": 1, "delivered": 2, "read": 3}
BAILEYS_STATUS = {0: "failed", 2: "sent", 3: "delivered", 4: "read", 5: "read"}
OPTOUT_WORDS = {"stop", "unsubscribe", "opt out", "optout", "remove me"}

GROUP_SYNC_EVERY = 15 * 60          # seconds between full profile refreshes


def _ms_to_dt(ms) -> dt.datetime:
    try:
        return dt.datetime.fromtimestamp(float(ms) / 1000, dt.timezone.utc).replace(tzinfo=None)
    except Exception:
        return utcnow()


def _opt_ms(ms):
    return _ms_to_dt(ms) if ms else None


def _num(jid: str) -> str:
    return (jid or "").split("@")[0].split(":")[0]


# ================================================================ statuses
def _advance(d: Delivery, new_status: str) -> bool:
    """Move a campaign delivery row forward, never backward."""
    if new_status == "failed":
        if d.status != "failed":
            d.status = "failed"
            return True
        return False
    if d.status == "failed" or RANK.get(new_status, -1) <= RANK.get(d.status, -1):
        return False
    d.status = new_status
    now = utcnow()
    if new_status in ("delivered", "read") and not d.delivered_at:
        d.delivered_at = now
    if new_status == "read" and not d.read_at:
        d.read_at = now
    if new_status == "sent" and not d.sent_at:
        d.sent_at = now
    return True


def _advance_msg(m: WaMessage, new: str, at: dt.datetime) -> bool:
    """Move a message's own status forward from a server status event."""
    cur = m.status or "pending"
    if cur == "failed":
        return False                        # terminal
    if new == "failed":
        if cur in ("delivered", "read"):
            return False                    # a failure after delivery is noise
        m.status = "failed"
        m.failed_count = m.recipient_total or 1
        return True
    if m.chat_type == "group" and new in ("delivered", "read"):
        # Group delivered/read is derived from per recipient receipts. A
        # server event still proves the message left, so it is at least Sent.
        new = "sent"
    if RANK.get(new, -1) <= RANK.get(cur, -1):
        return False
    m.status = new
    if new in ("delivered", "read") and not m.delivered_at:
        m.delivered_at = at
    if new == "read" and not m.read_at:
        m.read_at = at
    return True


def _upsert_receipt(s, msg_id: str, participant: str, delivered_at, read_at) -> WaReceipt:
    """One row per (message, recipient). Timestamps are set once, first wins."""
    rc = s.scalar(select(WaReceipt).where(WaReceipt.msg_id == msg_id,
                                          WaReceipt.participant == participant))
    if rc is None:
        rc = WaReceipt(msg_id=msg_id, participant=participant)
        s.add(rc)
    if read_at and not rc.read_at:
        rc.read_at = read_at
    if (delivered_at or read_at) and not rc.delivered_at:
        rc.delivered_at = delivered_at or read_at
    if rc.read_at and rc.delivered_at and rc.delivered_at > rc.read_at:
        rc.delivered_at = rc.read_at        # out of order events: delivery precedes read
    return rc


def self_ids(s, me_jid: str) -> set[str]:
    """Every id this account appears under: its number and its private id.
    WhatsApp sends receipts to all of an account's own devices too, and those
    must never count as recipients."""
    me = _num(me_jid)
    if not me:
        return set()
    ids = {me}
    for jid, alt in s.execute(select(GroupMember.jid, GroupMember.alt_jid)).all():
        if _num(jid) == me and alt:
            ids.add(_num(alt))
        elif _num(alt) == me and jid:
            ids.add(_num(jid))
    return ids


def recompute_message(s, m: WaMessage, mine: set[str] | None = None):
    """Derive counters, first delivery/read times and status from receipt rows."""
    if not m.from_me:
        return
    mine = mine if mine is not None else self_ids(s, m.sender_jid)
    rows = [r for r in s.scalars(select(WaReceipt).where(WaReceipt.msg_id == m.msg_id))
            if _num(r.participant) not in mine]
    delivered = [r for r in rows if r.delivered_at]
    read = [r for r in rows if r.read_at]
    m.delivered_count, m.read_count = len(delivered), len(read)
    if delivered:
        first = min(r.delivered_at for r in delivered)
        if not m.delivered_at or first < m.delivered_at:
            m.delivered_at = first
    if read:
        first = min(r.read_at for r in read)
        if not m.read_at or first < m.read_at:
            m.read_at = first
    if m.status == "failed":
        m.failed_count = m.recipient_total or 1
        return
    m.failed_count = 0
    # A receipt from someone who has since left still counts: they received it.
    total = max(m.recipient_total or (1 if m.chat_type == "individual" else 0), len(delivered))
    derived = None
    if m.chat_type == "individual":
        derived = "read" if read else ("delivered" if delivered else None)
    elif total:
        derived = "read" if len(read) >= total else ("delivered" if len(delivered) >= total else None)
    if (delivered or read) and RANK.get(m.status or "pending", 0) < RANK["sent"]:
        m.status = "sent"                   # any receipt proves the server took it
    if derived and RANK[derived] > RANK.get(m.status or "pending", 0):
        m.status = derived
    d = s.scalar(select(Delivery).where(Delivery.provider_message_id == m.msg_id))
    if d is not None:
        d.read_count = len(read)


def apply_receipts(items: list[dict]) -> dict:
    """Apply provider status events and per recipient receipts. Idempotent:
    replaying the same batch leaves every row and counter unchanged."""
    stats = {"seen": len(items), "advanced": 0, "participant_receipts": 0, "unmatched": 0}
    if not items:
        return stats
    with SessionLocal() as s:
        touched: set[str] = set()
        for it in items:
            mid = it.get("id") or ""
            if not mid:
                continue
            d = s.scalar(select(Delivery).where(Delivery.provider_message_id == mid))
            msgs = list(s.scalars(select(WaMessage).where(WaMessage.msg_id == mid,
                                                          WaMessage.from_me.is_(True))))
            ts = _opt_ms(it.get("ts_ms")) or utcnow()

            if it.get("kind") == "receipt":
                user = it.get("user") or ""
                if not user:
                    continue
                d_at = _opt_ms(it.get("delivered_ms")) or (ts if it.get("delivered") else None)
                r_at = _opt_ms(it.get("read_ms")) or (ts if it.get("read") else None)
                _upsert_receipt(s, mid, user, d_at if it.get("delivered") else None,
                                r_at if it.get("read") else None)
                stats["participant_receipts"] += 1
                touched.add(mid)
                if d is not None:
                    target = "read" if it.get("read") else ("delivered" if it.get("delivered") else None)
                    if target and _advance(d, target):
                        stats["advanced"] += 1
                continue

            mapped = BAILEYS_STATUS.get(it.get("status"))
            if not mapped:
                continue
            if d is not None and _advance(d, mapped):
                stats["advanced"] += 1
                if mapped == "failed" and it.get("error"):
                    err = it["error"]
                    d.error_code = err.get("code")
                    d.error_title = str(err.get("title", ""))[:280]
            for m in msgs:
                if mapped == "failed" and it.get("error"):
                    m.error = str(it["error"].get("title", ""))[:500]
                if m.chat_type == "individual" and mapped in ("delivered", "read"):
                    # One to one receipts arrive as status events; record the
                    # single recipient so the recipient view is uniform.
                    _upsert_receipt(s, mid, m.chat_jid,
                                    ts if mapped == "delivered" else None,
                                    ts if mapped == "read" else None)
                    touched.add(mid)
                if _advance_msg(m, mapped, ts):
                    stats["advanced"] += 1
            if d is None and not msgs:
                stats["unmatched"] += 1
        s.flush()
        for mid in touched:
            for m in s.scalars(select(WaMessage).where(WaMessage.msg_id == mid,
                                                       WaMessage.from_me.is_(True))):
                recompute_message(s, m)
            d = s.scalar(select(Delivery).where(Delivery.provider_message_id == mid))
            if d is not None:
                d.read_count = s.scalar(select(func.count()).select_from(WaReceipt).where(
                    WaReceipt.msg_id == mid, WaReceipt.read_at.is_not(None))) or 0
        s.commit()
    return stats


# ================================================================ messages
# Private id -> conversation, learnt from echoes of our own messages.
_ALIASES: dict[str, str] = {}


def _individual_allowlist(s) -> dict[str, str]:
    """Numbers this platform has messaged, mapped to the chat id they were
    stored under. Only these one to one chats are ever recorded: the linked
    account's personal conversations are not."""
    out = {}
    for jid, number in s.execute(select(WaMessage.chat_jid, WaMessage.peer_number)
                                 .where(WaMessage.chat_type == "individual",
                                        WaMessage.sent_via == "platform")
                                 .distinct()).all():
        out[_num(jid)] = jid
        if number:
            out[_num(number)] = jid
    for jid, number in s.execute(select(DirectChat.jid, DirectChat.number)).all():
        out[_num(jid)] = jid
        if number:
            out[_num(number)] = jid
    return out


def apply_messages(items: list[dict]) -> dict:
    """Store messages and reactions. Idempotent: history sync, live delivery
    and the platform's own record can all report the same message; it is
    stored once, keyed by its WhatsApp message id."""
    stats = {"seen": len(items), "stored": 0, "reactions": 0, "replies_to_campaigns": 0,
             "optouts": 0, "unknown_group": 0, "personal_skipped": 0}
    if not items:
        return stats
    with SessionLocal() as s:
        gid_cache: dict[str, int | None] = {}
        allow = _individual_allowlist(s)

        def gid_for(jid: str):
            if jid not in gid_cache:
                gid_cache[jid] = s.scalar(select(Group.id).where(Group.wa_group_id == jid))
            return gid_cache[jid]

        for it in items:
            chat = it.get("chat") or ""
            if not chat:
                continue
            ctype = it.get("chat_type") or ("group" if chat.endswith("@g.us") else "individual")
            if ctype == "individual":
                mid0 = it.get("id") or ""
                if it.get("from_me") and mid0:
                    known = s.scalar(select(WaMessage).where(WaMessage.msg_id == mid0))
                    if known is not None:
                        # WhatsApp echoed one of our messages, possibly under a
                        # private id instead of the phone number. Learn the alias
                        # so replies under that id reach the same conversation.
                        if _num(chat) != _num(known.chat_jid):
                            _ALIASES[_num(chat)] = known.chat_jid
                        continue
                canon = (allow.get(_num(chat)) or allow.get(_num(it.get("chat_alt") or ""))
                         or _ALIASES.get(_num(chat)))
                if not canon:
                    stats["personal_skipped"] += 1
                    continue
                chat = canon
            ts = _ms_to_dt(it.get("ts"))

            if it.get("kind") == "reaction":
                target = it.get("target_id") or ""
                sender = it.get("sender") or ""
                r = s.scalar(select(WaReaction).where(WaReaction.target_msg_id == target,
                                                      WaReaction.sender_jid == sender))
                if not it.get("emoji"):              # empty emoji = reaction removed
                    if r is not None:
                        s.delete(r)
                else:
                    if r is None:
                        r = WaReaction(chat_jid=chat, target_msg_id=target, sender_jid=sender)
                        s.add(r)
                    r.emoji, r.sender_name, r.ts = it["emoji"][:16], it.get("sender_name", ""), ts
                s.flush()
                cnt = s.scalar(select(func.count()).select_from(WaReaction)
                               .where(WaReaction.target_msg_id == target)) or 0
                for m in s.scalars(select(WaMessage).where(WaMessage.msg_id == target)):
                    m.reaction_count = cnt
                d = s.scalar(select(Delivery).where(Delivery.provider_message_id == target))
                if d is not None and it.get("emoji") and not it.get("from_me"):
                    s.add(Interaction(campaign_id=d.campaign_id, group_id=d.group_id,
                                      kind="reaction", text=it["emoji"][:16], ts=ts))
                stats["reactions"] += 1
                continue

            mid = it.get("id") or ""
            # keyed on the message id alone: the same message can surface under
            # a phone number id and under a private id
            if s.scalar(select(WaMessage.id).where(WaMessage.msg_id == mid)):
                continue
            group_id = gid_for(chat) if ctype == "group" else None
            if ctype == "group" and group_id is None:
                stats["unknown_group"] += 1
            from_me = bool(it.get("from_me"))
            d_own = s.scalar(select(Delivery).where(Delivery.provider_message_id == mid)) \
                if from_me else None
            total = 0
            if from_me:
                if ctype == "individual":
                    total = 1
                elif group_id:
                    g = s.get(Group, group_id)
                    total = max(0, (g.member_count or 0) - 1)
            m = WaMessage(
                msg_id=mid, chat_jid=chat, group_id=group_id, chat_type=ctype,
                sender_jid=it.get("sender", ""), sender_name=(it.get("sender_name") or "")[:160],
                from_me=from_me, ts=ts, mtype=(it.get("type") or "")[:40],
                text=(it.get("text") or "")[:2000], quoted_id=it.get("quoted_id") or "",
                from_history=bool(it.get("history")),
                campaign_id=d_own.campaign_id if d_own else None,
                status="sent" if from_me else "", recipient_total=total,
                sent_via=("campaign" if d_own else "phone") if from_me else "")
            s.add(m)
            s.flush()
            if from_me:
                recompute_message(s, m)     # receipts may have arrived first
            stats["stored"] += 1

            # A reply is credited to a campaign only when it quotes the
            # campaign message. Ordinary chatter in the group is not a reply.
            q = it.get("quoted_id") or ""
            if q and not from_me:
                for parent in s.scalars(select(WaMessage).where(WaMessage.msg_id == q)):
                    parent.reply_count = (parent.reply_count or 0) + 1
                dq = s.scalar(select(Delivery).where(Delivery.provider_message_id == q))
                if dq is not None:
                    s.add(Interaction(campaign_id=dq.campaign_id, group_id=dq.group_id,
                                      kind="reply", text=(it.get("text") or "")[:500], ts=ts))
                    stats["replies_to_campaigns"] += 1

            txt = (it.get("text") or "").strip().lower()
            if txt in OPTOUT_WORDS and not from_me and group_id:
                last = s.scalar(select(Delivery).where(Delivery.group_id == group_id)
                                .order_by(Delivery.id.desc()))
                if last is not None:
                    s.add(Interaction(campaign_id=last.campaign_id, group_id=group_id,
                                      kind="optout", text=txt, ts=ts))
                    stats["optouts"] += 1
        s.commit()
    return stats


# ================================================================== groups
def apply_groups(groups: list[dict]) -> dict:
    """Upsert each real group, its profile and its member list."""
    stats = {"groups": len(groups), "added": 0, "updated": 0, "members": 0}
    with SessionLocal() as s:
        for g in groups:
            jid = g.get("id") or ""
            if not jid:
                continue
            row = s.scalar(select(Group).where(Group.wa_group_id == jid))
            if row is None:
                row = Group(wa_group_id=jid, name=g.get("subject", "Untitled group"),
                            category="Imported", source="linked_device")
                s.add(row)
                s.flush()
                stats["added"] += 1
            else:
                stats["updated"] += 1
            row.name = g.get("subject") or row.name
            row.member_count = int(g.get("size") or 0)

            parts = g.get("participants") or []
            meta = s.get(GroupMeta, row.id) or GroupMeta(group_id=row.id)
            meta.description = (g.get("desc") or "")[:4000]
            meta.owner_jid = g.get("owner") or ""
            meta.wa_created_at = _ms_to_dt(g["created"]) if g.get("created") else None
            meta.announce = bool(g.get("announce"))
            meta.restrict = bool(g.get("restrict"))
            meta.ephemeral_seconds = int(g.get("ephemeral") or 0)
            meta.is_community = bool(g.get("is_community"))
            meta.admin_count = sum(1 for p in parts if p.get("admin"))
            meta.synced_at = utcnow()
            s.merge(meta)

            if parts:
                s.execute(delete(GroupMember).where(GroupMember.group_id == row.id))
                for p in parts:
                    s.add(GroupMember(group_id=row.id, jid=p.get("id", ""),
                                      alt_jid=p.get("alt", "") or "",
                                      name=(p.get("name") or "")[:160],
                                      role=p.get("admin") or "member"))
                stats["members"] += len(parts)
        s.commit()
    return stats


def recompute_all():
    """Re-derive every message this account sent from its receipt rows. Run
    at start up. Status is fully derivable for everything that is neither
    Pending nor Failed, so those are rebuilt from Sent upwards; this also
    corrects anything recorded under earlier, looser rules."""
    with SessionLocal() as s:
        cache: dict[str, set[str]] = {}
        for m in s.scalars(select(WaMessage).where(WaMessage.from_me.is_(True))):
            if m.status in ("sent", "delivered", "read"):
                m.status = "sent"
                m.delivered_at = m.read_at = None
            key = _num(m.sender_jid)
            if key not in cache:
                cache[key] = self_ids(s, m.sender_jid)
            recompute_message(s, m, cache[key])
        s.commit()


# ================================================================ pollers
async def poll_loop(interval: float = 3.0):
    """Background consumer. Cheap when the bridge is absent: every drain
    returns an empty list and the loop waits again."""
    adapter = adapters.get("linked_device")
    last_sync = 0.0
    loop = asyncio.get_event_loop()
    try:
        recompute_all()
    except Exception:
        pass
    while True:
        await asyncio.sleep(interval)
        try:
            # Messages first, so a receipt for a message seen in the same
            # cycle finds its row.
            msgs = await adapter.drain_messages()
            if msgs:
                apply_messages(msgs)
            rc = await adapter.drain_receipts()
            if rc:
                apply_receipts(rc)
            # The inbound stream is superseded by the message stream above.
            # Drain it so the bridge buffer does not fill, but do not count it
            # again: that would credit ordinary group chatter as replies.
            await adapter.drain_inbound()

            if loop.time() - last_sync > GROUP_SYNC_EVERY:
                groups = await adapter.groups_full()
                if groups:
                    apply_groups(groups)
                    last_sync = loop.time()
        except Exception:
            pass
