# -*- coding: utf-8 -*-
"""Data model. Delivery states mirror the WhatsApp status webhook vocabulary
(sent, delivered, read, failed) so that the simulator, the Cloud API adapter
and the linked device adapter all report into the same schema."""
import datetime as dt
import json
from sqlalchemy import (create_engine, String, Integer, Float, Text, DateTime,
                        ForeignKey, Boolean, Index, event)
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column, relationship,
                            sessionmaker)
from config import DB_URL


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------- identity
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(256))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    last_login: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class Session(Base):
    __tablename__ = "sessions"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    user: Mapped[User] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor: Mapped[str] = mapped_column(String(160), default="system")
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity: Mapped[str] = mapped_column(String(60), default="")
    entity_id: Mapped[str] = mapped_column(String(60), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    ip: Mapped[str] = mapped_column(String(64), default="")


# ----------------------------------------------------------------- groups
class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    wa_group_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    category: Mapped[str] = mapped_column(String(80), default="", index=True)
    folder: Mapped[str] = mapped_column(String(80), default="", index=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    region: Mapped[str] = mapped_column(String(80), default="")
    source: Mapped[str] = mapped_column(String(40), default="import")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def tags(self) -> list[str]:
        try:
            return json.loads(self.tags_json or "[]")
        except Exception:
            return []

    def as_dict(self) -> dict:
        return {
            "id": self.id, "wa_group_id": self.wa_group_id, "name": self.name,
            "category": self.category, "folder": self.folder, "tags": self.tags,
            "member_count": self.member_count, "region": self.region,
            "active": self.active, "source": self.source,
        }


Index("ix_groups_cat_folder", Group.category, Group.folder)


class GroupList(Base):
    """A saved, reusable campaign list."""
    __tablename__ = "group_lists"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class GroupListMember(Base):
    __tablename__ = "group_list_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("group_lists.id"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)


# ------------------------------------------------------------ media/templates
class Media(Base):
    __tablename__ = "media"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(260))
    mime: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    stored_path: Mapped[str] = mapped_column(String(400))
    kind: Mapped[str] = mapped_column(String(24), default="document")
    # tracked = delivered via a landing endpoint so that views are measurable
    tracked: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    def as_dict(self) -> dict:
        return {"id": self.id, "filename": self.filename, "mime": self.mime,
                "size_bytes": self.size_bytes, "kind": self.kind,
                "tracked": self.tracked}


class Template(Base):
    __tablename__ = "templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    body: Mapped[str] = mapped_column(Text, default="")
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "body": self.body,
                "media_id": self.media_id}


# -------------------------------------------------------------- campaigns
CAMPAIGN_STATES = ("draft", "scheduled", "running", "paused", "completed",
                   "partially_failed", "cancelled")


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text, default="")
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media.id"), nullable=True)
    link_url: Mapped[str] = mapped_column(String(600), default="")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    channel: Mapped[str] = mapped_column(String(24), default="simulator")
    scheduled_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    recurrence: Mapped[str] = mapped_column(String(40), default="")
    recur_until: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    target_count: Mapped[int] = mapped_column(Integer, default=0)

    media: Mapped[Media | None] = relationship()


class Delivery(Base):
    """One row per group per campaign. This is the per-group success and
    failure log required by FR-15."""
    __tablename__ = "deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    provider_message_id: Mapped[str] = mapped_column(String(120), default="")
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_title: Mapped[str] = mapped_column(String(300), default="")
    error_detail: Mapped[str] = mapped_column(Text, default="")
    queued_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    read_count: Mapped[int] = mapped_column(Integer, default=0)


Index("ix_deliv_camp_status", Delivery.campaign_id, Delivery.status)


# --------------------------------------------------------------- tracking
class TrackedLink(Base):
    """A short link unique to (campaign, group). This is what makes click
    analytics attributable to an individual group."""
    __tablename__ = "tracked_links"
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    target_url: Mapped[str] = mapped_column(String(600))
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    unique_clicks: Mapped[int] = mapped_column(Integer, default=0)


class LinkEvent(Base):
    __tablename__ = "link_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("tracked_links.id"), index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    visitor_hash: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")


class MediaEvent(Base):
    """A media view recorded because the file was delivered through a tracked
    landing endpoint rather than as a direct attachment (refer feasibility
    row M5: a direct attachment cannot be measured)."""
    __tablename__ = "media_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media.id"), index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="view")
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Interaction(Base):
    """Inbound replies and opt-out requests attributed to a campaign."""
    __tablename__ = "interactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="reply")
    text: Mapped[str] = mapped_column(Text, default="")
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Snapshot(Base):
    """Immutable analytics snapshot at 15m, 1h, 3h and 8h after despatch
    completes (FR-16)."""
    __tablename__ = "snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    label: Mapped[str] = mapped_column(String(8))
    taken_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")


class EventLog(Base):
    """Real time operational log stream shown on the live monitor (FR-25)."""
    __tablename__ = "event_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"),
                                                    nullable=True, index=True)
    level: Mapped[str] = mapped_column(String(12), default="info")
    message: Mapped[str] = mapped_column(Text, default="")


# ------------------------------------------------- linked account observations
# Everything below is what the linked WhatsApp account itself can see. It is
# stored locally and never leaves this machine.

class GroupMeta(Base):
    """Profile of a real group as reported by WhatsApp."""
    __tablename__ = "group_meta"
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_jid: Mapped[str] = mapped_column(String(120), default="")
    wa_created_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    announce: Mapped[bool] = mapped_column(Boolean, default=False)   # admins only send
    restrict: Mapped[bool] = mapped_column(Boolean, default=False)   # admins only edit
    ephemeral_seconds: Mapped[int] = mapped_column(Integer, default=0)
    is_community: Mapped[bool] = mapped_column(Boolean, default=False)
    admin_count: Mapped[int] = mapped_column(Integer, default=0)
    synced_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class GroupMember(Base):
    __tablename__ = "group_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    jid: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    role: Mapped[str] = mapped_column(String(16), default="member")  # member|admin|superadmin
    # WhatsApp may address the same member by phone number or by a private
    # "LID" id. Receipts can arrive under either, so both are kept.
    alt_jid: Mapped[str] = mapped_column(String(120), default="", index=True)


class DirectChat(Base):
    """A one to one conversation the platform has opened. Its existence is
    what allows that person's replies to be stored: the linked account's other
    personal conversations are never recorded."""
    __tablename__ = "direct_chats"
    jid: Mapped[str] = mapped_column(String(120), primary_key=True)
    number: Mapped[str] = mapped_column(String(32), default="", index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class WaMessage(Base):
    """A message seen in a real group, sent by anyone including this account."""
    __tablename__ = "wa_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    msg_id: Mapped[str] = mapped_column(String(80), index=True)
    chat_jid: Mapped[str] = mapped_column(String(120), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True, index=True)
    sender_jid: Mapped[str] = mapped_column(String(120), default="", index=True)
    sender_name: Mapped[str] = mapped_column(String(160), default="")
    from_me: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    mtype: Mapped[str] = mapped_column(String(40), default="conversation")
    text: Mapped[str] = mapped_column(Text, default="")
    quoted_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    from_history: Mapped[bool] = mapped_column(Boolean, default=False)
    # Receipts exist only for messages this account sent: WhatsApp sends read
    # receipts to the sender and to nobody else.
    delivered_count: Mapped[int] = mapped_column(Integer, default=0)
    read_count: Mapped[int] = mapped_column(Integer, default=0)
    reaction_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True)

    # ---- message level delivery metadata (messages this account sent) ----
    # Message -> WaReceipt (one row per recipient) -> delivered_at / read_at.
    # The counters below are always recomputed from the receipt rows, never
    # incremented, so a duplicated provider event cannot inflate them.
    chat_type: Mapped[str] = mapped_column(String(12), default="group", index=True)  # group|individual
    status: Mapped[str] = mapped_column(String(12), default="", index=True)  # pending|sent|delivered|read|failed
    recipient_total: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    delivered_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    peer_name: Mapped[str] = mapped_column(String(160), default="")      # individual recipient name
    peer_number: Mapped[str] = mapped_column(String(32), default="")     # individual recipient number
    sent_via: Mapped[str] = mapped_column(String(12), default="")        # platform|phone|campaign


Index("ux_wa_msg", WaMessage.chat_jid, WaMessage.msg_id, unique=True)


class WaReceipt(Base):
    """Per participant delivery and read receipt for a message this account sent.
    This is the data WhatsApp shows under Message info."""
    __tablename__ = "wa_receipts"
    id: Mapped[int] = mapped_column(primary_key=True)
    msg_id: Mapped[str] = mapped_column(String(80), index=True)
    participant: Mapped[str] = mapped_column(String(120))
    delivered_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


Index("ux_wa_receipt", WaReceipt.msg_id, WaReceipt.participant, unique=True)


class WaReaction(Base):
    __tablename__ = "wa_reactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_jid: Mapped[str] = mapped_column(String(120), index=True)
    target_msg_id: Mapped[str] = mapped_column(String(80), index=True)
    sender_jid: Mapped[str] = mapped_column(String(120), default="")
    sender_name: Mapped[str] = mapped_column(String(160), default="")
    emoji: Mapped[str] = mapped_column(String(16), default="")
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


Index("ux_wa_reaction", WaReaction.target_msg_id, WaReaction.sender_jid, unique=True)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


# ------------------------------------------------------------------ engine
engine = create_engine(DB_URL, future=True,
                       connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _sqlite_pragmas(conn, _rec):
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db():
    Base.metadata.create_all(engine)
    migrate()


# Columns added after the first release. create_all() creates missing tables
# but never alters existing ones, so new columns are added here. Idempotent.
_ADDED_COLUMNS = {
    "wa_messages": [
        ("chat_type", "VARCHAR(12) DEFAULT 'group'"),
        ("status", "VARCHAR(12) DEFAULT ''"),
        ("recipient_total", "INTEGER DEFAULT 0"),
        ("failed_count", "INTEGER DEFAULT 0"),
        ("delivered_at", "DATETIME"),
        ("read_at", "DATETIME"),
        ("error", "TEXT DEFAULT ''"),
        ("peer_name", "VARCHAR(160) DEFAULT ''"),
        ("peer_number", "VARCHAR(32) DEFAULT ''"),
        ("sent_via", "VARCHAR(12) DEFAULT ''"),
    ],
    "group_members": [("alt_jid", "VARCHAR(120) DEFAULT ''")],
}


def migrate():
    from sqlalchemy import text
    with engine.begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            have = {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}
            for name, ddl in cols:
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_wa_messages_chat_type ON wa_messages (chat_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_wa_messages_status ON wa_messages (status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_group_members_alt_jid ON group_members (alt_jid)"))
        # Backfill: messages captured before this release.
        conn.execute(text("UPDATE wa_messages SET chat_type='group' WHERE chat_type IS NULL OR chat_type=''"))
        conn.execute(text("UPDATE wa_messages SET sent_via = CASE WHEN campaign_id IS NOT NULL "
                          "THEN 'campaign' ELSE 'phone' END WHERE from_me=1 AND (sent_via IS NULL OR sent_via='')"))
        # Baseline only; the receipt consumer re-derives the real status at start up.
        conn.execute(text("UPDATE wa_messages SET status='sent' WHERE from_me=1 AND (status IS NULL OR status='')"))
        conn.execute(text("UPDATE wa_messages SET recipient_total = (SELECT MAX(COALESCE(g.member_count,0)-1, 0) "
                          "FROM groups g WHERE g.id = wa_messages.group_id) "
                          "WHERE from_me=1 AND chat_type='group' AND group_id IS NOT NULL "
                          "AND (recipient_total IS NULL OR recipient_total=0)"))
