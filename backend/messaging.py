# -*- coding: utf-8 -*-
"""Message level delivery metadata for group and one to one messages.

A sent message is one WaMessage row. Its recipients are WaReceipt rows, one
per recipient, carrying delivered_at and read_at as reported by WhatsApp.
Everything shown in a message's details is derived from those two tables.

What WhatsApp does and does not report, so the interface can say it plainly:
  - Delivered and read are reported per recipient for messages this account
    sends, in groups and one to one.
  - A recipient who has switched read receipts off never reports "read" in a
    one to one chat. In group chats read receipts are always sent.
  - Failure is reported per message, not per group member: a failed group
    send failed for every recipient.
"""
import datetime as dt
import re

from sqlalchemy import select, func, desc, or_

from db import (SessionLocal, Group, GroupMember, WaMessage, WaReceipt, Campaign, utcnow)
from group_insights import mask

DEFAULT_COUNTRY_CODE = "91"


def normalize_number(raw: str, default_cc: str = DEFAULT_COUNTRY_CODE) -> str:
    """Digits only, in full international form. A 10 digit number is taken to
    be local and gets the default country code. Raises ValueError."""
    raw = (raw or "").strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("00"):
        digits = digits[2:]
    elif not raw.startswith("+") and len(digits) == 10:
        digits = default_cc + digits
    elif not raw.startswith("+") and len(digits) == 11 and digits.startswith("0"):
        digits = default_cc + digits[1:]
    if not 8 <= len(digits) <= 15:
        raise ValueError("Enter a WhatsApp number with country code, for example +91 98765 43210.")
    return digits


def pretty_number(digits: str) -> str:
    d = re.sub(r"\D", "", digits or "")
    if d.startswith("91") and len(d) == 12:
        return f"+91 {d[2:7]} {d[7:]}"
    return "+" + d if d else ""


def _num(jid: str) -> str:
    return (jid or "").split("@")[0].split(":")[0]


# ================================================================== writes
def record_sent(*, chat_jid: str, chat_type: str, group_id: int | None, msg_id: str,
                text: str, mtype: str, quoted_id: str, me_jid: str, recipient_total: int,
                peer_name: str = "", peer_number: str = "") -> None:
    """Store an outgoing message as Pending. It becomes Sent only when
    WhatsApp's server acknowledges it; the send call accepting it proves
    nothing more. The bridge later echoes the same message and is ignored."""
    if not msg_id:
        return
    with SessionLocal() as s:
        if s.scalar(select(WaMessage.id).where(WaMessage.msg_id == msg_id)):
            return
        s.add(WaMessage(msg_id=msg_id, chat_jid=chat_jid, group_id=group_id,
                        chat_type=chat_type, sender_jid=me_jid, sender_name="You",
                        from_me=True, ts=utcnow(), mtype=mtype, text=text[:2000],
                        quoted_id=quoted_id or "", status="pending",
                        recipient_total=recipient_total, sent_via="platform",
                        peer_name=peer_name[:160], peer_number=peer_number[:32]))
        s.commit()


def record_failed(*, chat_jid: str, chat_type: str, group_id: int | None, text: str,
                  mtype: str, me_jid: str, recipient_total: int, error: str,
                  peer_name: str = "", peer_number: str = "") -> str:
    """A send that never reached WhatsApp still belongs in the history, marked
    Failed with the reason, so it is visible and can be retried."""
    import secrets
    local_id = "local-" + secrets.token_hex(10)
    with SessionLocal() as s:
        s.add(WaMessage(msg_id=local_id, chat_jid=chat_jid or f"{peer_number}@s.whatsapp.net",
                        group_id=group_id, chat_type=chat_type, sender_jid=me_jid,
                        sender_name="You", from_me=True, ts=utcnow(), mtype=mtype,
                        text=text[:2000], status="failed", recipient_total=recipient_total,
                        failed_count=recipient_total or 1, error=error[:500],
                        sent_via="platform", peer_name=peer_name[:160],
                        peer_number=peer_number[:32]))
        s.commit()
    return local_id


# =================================================================== reads
def _summary(m: WaMessage, group_name: str | None, campaign_code: str | None) -> dict:
    # a receipt from someone who has since left still counts as a recipient
    total = max(m.recipient_total or (1 if m.chat_type == "individual" else 0),
                m.delivered_count or 0)
    failed = m.failed_count if m.status == "failed" else 0
    delivered = m.delivered_count or 0
    read = m.read_count or 0
    return {
        "msg_id": m.msg_id, "type": m.chat_type, "status": m.status or "sent",
        "to": group_name if m.chat_type == "group" else (m.peer_name or pretty_number(m.peer_number or _num(m.chat_jid))),
        "to_number": pretty_number(m.peer_number or _num(m.chat_jid)) if m.chat_type == "individual" else None,
        "group_id": m.group_id, "text": m.text, "mtype": m.mtype,
        "sent_at": m.ts.isoformat() if m.ts else None,
        "delivered_at": m.delivered_at.isoformat() if m.delivered_at else None,
        "read_at": m.read_at.isoformat() if m.read_at else None,
        "total": total, "delivered": delivered, "read": read, "failed": failed,
        "pending_delivery": max(0, total - delivered - failed),
        "not_read": max(0, delivered - read),
        "error": m.error or "", "sent_via": m.sent_via or "", "campaign": campaign_code,
        "reactions": m.reaction_count or 0, "replies": m.reply_count or 0,
    }


def list_messages(kind: str = "", status: str = "", q: str = "", source: str = "",
                  page: int = 1, size: int = 25) -> dict:
    size = max(1, min(100, size))
    with SessionLocal() as s:
        stmt = (select(WaMessage, Group.name, Campaign.code)
                .outerjoin(Group, Group.id == WaMessage.group_id)
                .outerjoin(Campaign, Campaign.id == WaMessage.campaign_id)
                .where(WaMessage.from_me.is_(True)))
        if kind in ("group", "individual"):
            stmt = stmt.where(WaMessage.chat_type == kind)
        if status:
            stmt = stmt.where(WaMessage.status == status)
        if source in ("platform", "phone", "campaign"):
            stmt = stmt.where(WaMessage.sent_via == source)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(WaMessage.text.like(like), Group.name.like(like),
                                  WaMessage.peer_name.like(like), WaMessage.peer_number.like(like)))
        total = s.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = s.execute(stmt.order_by(desc(WaMessage.ts))
                         .offset((page - 1) * size).limit(size)).all()
        counts = dict(s.execute(select(WaMessage.status, func.count())
                                .where(WaMessage.from_me.is_(True))
                                .group_by(WaMessage.status)).all())
    return {"total": total, "page": page, "size": size,
            "items": [_summary(m, gname, code) for m, gname, code in rows],
            "status_counts": {k or "sent": v for k, v in counts.items()}}


def message_details(msg_id: str, me_jid: str = "") -> dict | None:
    """Message metadata plus recipient level status."""
    with SessionLocal() as s:
        m = s.scalar(select(WaMessage).where(WaMessage.msg_id == msg_id)
                     .order_by(WaMessage.from_me.desc()))
        if m is None:
            return None
        g = s.get(Group, m.group_id) if m.group_id else None
        camp = s.get(Campaign, m.campaign_id) if m.campaign_id else None
        receipts = list(s.scalars(select(WaReceipt).where(WaReceipt.msg_id == msg_id)))
        members = list(s.scalars(select(GroupMember).where(GroupMember.group_id == m.group_id))) \
            if m.group_id else []
        out = _summary(m, g.name if g else None, camp.code if camp else None)
        out["from_me"] = m.from_me
        failed_all = m.status == "failed"

        def row(name, ident, rc):
            if failed_all:
                st = "failed"
            elif rc is not None and rc.read_at:
                st = "read"
            elif rc is not None and rc.delivered_at:
                st = "delivered"
            else:
                st = "pending"
            return {"recipient": name, "id": ident, "status": st,
                    "delivered_at": rc.delivered_at.isoformat() if rc is not None and rc.delivered_at else None,
                    "read_at": rc.read_at.isoformat() if rc is not None and rc.read_at else None}

        recipients = []
        if m.chat_type == "individual":
            rc = receipts[0] if receipts else None
            recipients.append(row(m.peer_name or pretty_number(m.peer_number or _num(m.chat_jid)),
                                  pretty_number(m.peer_number or _num(m.chat_jid)), rc))
        else:
            from receipts import self_ids
            mine = self_ids(s, me_jid or m.sender_jid)
            by_key = {}
            for rc in receipts:
                by_key[_num(rc.participant)] = rc
            used = set()
            for gm in members:
                keys = [k for k in (_num(gm.jid), _num(gm.alt_jid)) if k]
                if mine & set(keys):
                    continue                 # the sender is not a recipient
                rc = next((by_key[k] for k in keys if k in by_key), None)
                if rc is not None:
                    used.add(_num(rc.participant))
                recipients.append(row(gm.name or mask(gm.jid, me_jid), mask(gm.jid, me_jid), rc))
            # receipts from people no longer in the member list
            for k, rc in by_key.items():
                if k not in used and k not in mine:
                    r = row(mask(rc.participant, me_jid), mask(rc.participant, me_jid), rc)
                    r["former_member"] = True
                    recipients.append(r)
        order = {"read": 0, "delivered": 1, "pending": 2, "failed": 3}
        recipients.sort(key=lambda r: (order[r["status"]], r["read_at"] or r["delivered_at"] or "", r["recipient"]))
        out["recipients"] = recipients
        out["recipient_counts"] = {k: sum(1 for r in recipients if r["status"] == k) for k in order}
        out["member_list_synced"] = bool(members) or m.chat_type == "individual"
        if m.chat_type == "group":
            # The details card shows the group's full membership, which includes the
            # sending account. "total" stays the recipient count and keeps driving the
            # delivery arithmetic, so the two differ by one on purpose.
            out["member_total"] = max((g.member_count if g else 0) or 0,
                                      len(members)) or out["total"]
        out["notes"] = []
        if m.chat_type == "individual" and out["status"] == "delivered":
            out["notes"].append("Delivered but not read. The recipient may have read receipts switched off, "
                                "in which case WhatsApp never reports a read in one to one chats.")
        if m.chat_type == "group":
            out["notes"].append("WhatsApp reports failures per message, not per member: a failed group "
                                "message failed for every recipient.")
        if out["status"] == "pending":
            out["notes"].append("Pending: accepted for sending, not yet acknowledged by WhatsApp's server.")
    return out
