# -*- coding: utf-8 -*-
"""Analytics and the interval snapshot engine.

Every metric produced here carries the feasibility id it corresponds to in
the proposal's feasibility table, so the dashboard can state on what basis
each number exists:

  M1 groups reached          delivery engine / sent + delivered status
  M2 delivery failures       failed status plus numeric error code
  M3 pending deliveries      derived from the gap between sent and delivered
  M4 link clicks             per group tracked short links
  M5 media views             tracked landing endpoint only
  M6 user interactions       inbound replies and opt outs
  M7 engagement metrics      composite of the above
  M8 custom metrics          computed over the collected data set
  M9 read statistics         read status, aggregated per group
"""
import json
import datetime as dt

from sqlalchemy import select, func

import config
from db import (SessionLocal, Campaign, Delivery, Group, TrackedLink, LinkEvent,
                MediaEvent, Interaction, Snapshot, utcnow)

TERMINAL_OK = ("delivered", "read")


def campaign_metrics(campaign_id: int, session=None) -> dict:
    own = session is None
    s = session or SessionLocal()
    try:
        camp = s.get(Campaign, campaign_id)
        if camp is None:
            return {}

        rows = s.execute(
            select(Delivery.status, func.count())
            .where(Delivery.campaign_id == campaign_id)
            .group_by(Delivery.status)).all()
        counts = {k: v for k, v in rows}
        targets = sum(counts.values())

        delivered = counts.get("delivered", 0)
        read = counts.get("read", 0)
        sent = counts.get("sent", 0)
        queued = counts.get("queued", 0)
        failed = counts.get("failed", 0)

        # M1: a group counts as reached once the platform has confirmation it
        # arrived. Messages still in flight are pending, not reached.
        reached = delivered + read
        pending = queued + sent

        # M9: read receipts in groups arrive aggregated, so we hold both the
        # number of groups that registered a read and the modelled member count.
        read_members = s.execute(
            select(func.coalesce(func.sum(Delivery.read_count), 0))
            .where(Delivery.campaign_id == campaign_id)).scalar() or 0

        # M2: failure reasons are machine readable, which is what lets the
        # retry policy separate transient from permanent.
        fail_rows = s.execute(
            select(Delivery.error_code, Delivery.error_title, func.count())
            .where(Delivery.campaign_id == campaign_id,
                   Delivery.status == "failed")
            .group_by(Delivery.error_code, Delivery.error_title)
            .order_by(func.count().desc())).all()
        failures = [{"code": c, "title": t, "count": n} for c, t, n in fail_rows]

        # M4
        clicks, unique_clicks = s.execute(
            select(func.coalesce(func.sum(TrackedLink.clicks), 0),
                   func.coalesce(func.sum(TrackedLink.unique_clicks), 0))
            .where(TrackedLink.campaign_id == campaign_id)).one()
        groups_clicked = s.execute(
            select(func.count(func.distinct(LinkEvent.group_id)))
            .where(LinkEvent.campaign_id == campaign_id)).scalar() or 0

        # M5
        media_views = s.execute(
            select(func.count()).where(MediaEvent.campaign_id == campaign_id)
        ).scalar() or 0

        # M6
        replies = s.execute(
            select(func.count()).where(Interaction.campaign_id == campaign_id,
                                       Interaction.kind == "reply")).scalar() or 0
        optouts = s.execute(
            select(func.count()).where(Interaction.campaign_id == campaign_id,
                                       Interaction.kind == "optout")).scalar() or 0

        def pct(n, d):
            return round(100.0 * n / d, 2) if d else 0.0

        # M7: a composite index over what we actually collect, not a figure
        # reported by WhatsApp.
        engagement_index = round(
            0.45 * pct(read, reached or 1) / 100
            + 0.35 * pct(groups_clicked, reached or 1) / 100
            + 0.20 * pct(replies, reached or 1) / 100, 4)

        return {
            "campaign_id": campaign_id,
            "campaign_code": camp.code,
            "campaign_name": camp.name,
            "status": camp.status,
            "channel": camp.channel,
            "targets": targets,
            "M1_groups_reached": reached,
            "M1_reach_pct": pct(reached, targets),
            "M2_failures": failed,
            "M2_failure_pct": pct(failed, targets),
            "M2_failure_breakdown": failures,
            "M3_pending": pending,
            "M3_queued": queued,
            "M3_sent_awaiting_delivery": sent,
            "M9_groups_read": read,
            "M9_read_pct_of_reached": pct(read, reached),
            "M9_member_reads": int(read_members),
            "M4_clicks": int(clicks),
            "M4_unique_clicks": int(unique_clicks),
            "M4_groups_clicked": groups_clicked,
            "M4_ctr_pct": pct(groups_clicked, reached),
            "M5_media_views": media_views,
            "M6_replies": replies,
            "M6_optouts": optouts,
            "M7_engagement_index": engagement_index,
            "delivered_only": delivered,
            "started_at": camp.started_at.isoformat() if camp.started_at else None,
            "completed_at": camp.completed_at.isoformat() if camp.completed_at else None,
        }
    finally:
        if own:
            s.close()


def take_snapshot(campaign_id: int, label: str, session=None) -> dict:
    """Immutable snapshot at a defined interval after despatch completes."""
    own = session is None
    s = session or SessionLocal()
    try:
        existing = s.scalar(select(Snapshot).where(
            Snapshot.campaign_id == campaign_id, Snapshot.label == label))
        if existing:
            return json.loads(existing.metrics_json)
        metrics = campaign_metrics(campaign_id, session=s)
        metrics["snapshot_label"] = label
        metrics["snapshot_taken_at"] = utcnow().isoformat()
        s.add(Snapshot(campaign_id=campaign_id, label=label,
                       metrics_json=json.dumps(metrics)))
        if own:
            s.commit()
        return metrics
    finally:
        if own:
            s.close()


def snapshots_for(campaign_id: int) -> list[dict]:
    order = {lbl: i for i, (lbl, _) in enumerate(config.SNAPSHOT_INTERVALS)}
    with SessionLocal() as s:
        rows = list(s.scalars(select(Snapshot).where(
            Snapshot.campaign_id == campaign_id)))
    out = []
    for r in rows:
        try:
            m = json.loads(r.metrics_json)
        except Exception:
            m = {}
        m["label"] = r.label
        m["taken_at"] = r.taken_at.isoformat()
        out.append(m)
    out.sort(key=lambda m: order.get(m.get("label", ""), 99))
    return out


def snapshot_schedule(campaign_id: int) -> list[dict]:
    """What is due, and when, so the interface can show pending snapshots
    rather than leaving four empty rows unexplained."""
    with SessionLocal() as s:
        camp = s.get(Campaign, campaign_id)
        taken = {r.label: r.taken_at for r in s.scalars(
            select(Snapshot).where(Snapshot.campaign_id == campaign_id))}
    out = []
    base = camp.completed_at if camp and camp.completed_at else None
    for label, seconds in config.SNAPSHOT_INTERVALS:
        due = (base + dt.timedelta(seconds=config.scaled(seconds))) if base else None
        out.append({
            "label": label,
            "nominal_interval_seconds": seconds,
            "effective_interval_seconds": round(config.scaled(seconds), 2),
            "due_at": due.isoformat() if due else None,
            "taken": label in taken,
            "taken_at": taken[label].isoformat() if label in taken else None,
        })
    return out


# ------------------------------------------------------------- aggregations
def portfolio_summary() -> dict:
    with SessionLocal() as s:
        total_groups = s.scalar(select(func.count()).select_from(Group)) or 0
        active_groups = s.scalar(select(func.count()).select_from(Group)
                                 .where(Group.active.is_(True))) or 0
        campaigns = s.scalar(select(func.count()).select_from(Campaign)) or 0
        running = s.scalar(select(func.count()).select_from(Campaign)
                           .where(Campaign.status.in_(("running", "paused")))) or 0
        # A draft campaign has despatched nothing. Its queued rows are targets
        # a user selected, not messages, so they stay out of the delivery record.
        rows = s.execute(select(Delivery.status, func.count())
                         .join(Campaign, Campaign.id == Delivery.campaign_id)
                         .where(Campaign.status != "draft")
                         .group_by(Delivery.status)).all()
        counts = {k: v for k, v in rows}
        clicks = s.scalar(select(func.coalesce(func.sum(TrackedLink.clicks), 0))) or 0
        interactions = s.scalar(select(func.count()).select_from(Interaction)) or 0
    reached = counts.get("delivered", 0) + counts.get("read", 0)
    total = sum(counts.values())
    return {
        "groups_total": total_groups, "groups_active": active_groups,
        "campaigns_total": campaigns, "campaigns_running": running,
        "messages_total": total, "groups_reached": reached,
        "failures": counts.get("failed", 0),
        "pending": counts.get("queued", 0) + counts.get("sent", 0),
        "reads": counts.get("read", 0), "clicks": int(clicks),
        "interactions": interactions,
        "reach_pct": round(100.0 * reached / total, 2) if total else 0.0,
    }


def timeseries(campaign_id: int, buckets: int = 24) -> list[dict]:
    """Delivery and read progression over the life of the campaign, used for
    the campaign chart."""
    with SessionLocal() as s:
        camp = s.get(Campaign, campaign_id)
        if camp is None or camp.started_at is None:
            return []
        rows = list(s.execute(
            select(Delivery.sent_at, Delivery.delivered_at, Delivery.read_at,
                   Delivery.status)
            .where(Delivery.campaign_id == campaign_id)).all())
    if not rows:
        return []
    start = camp.started_at
    end = camp.completed_at or utcnow()
    marks = [r[2] for r in rows if r[2]] + [r[1] for r in rows if r[1]]
    if marks:
        end = max(end, max(marks))
    span = max(1.0, (end - start).total_seconds())
    width = span / buckets
    out = []
    for i in range(buckets):
        edge = start + dt.timedelta(seconds=width * (i + 1))
        out.append({
            "t": edge.isoformat(),
            "offset_sec": round(width * (i + 1), 1),
            "sent": sum(1 for r in rows if r[0] and r[0] <= edge),
            "delivered": sum(1 for r in rows if r[1] and r[1] <= edge),
            "read": sum(1 for r in rows if r[2] and r[2] <= edge),
        })
    return out


def group_performance(campaign_id: int, limit: int = 100) -> list[dict]:
    with SessionLocal() as s:
        rows = list(s.execute(
            select(Group.id, Group.name, Group.category, Group.member_count,
                   Delivery.status, Delivery.read_count, Delivery.error_code,
                   Delivery.error_title, Delivery.attempts)
            .join(Delivery, Delivery.group_id == Group.id)
            .where(Delivery.campaign_id == campaign_id)
            .limit(limit)).all())
        clicks = {gid: n for gid, n in s.execute(
            select(LinkEvent.group_id, func.count())
            .where(LinkEvent.campaign_id == campaign_id)
            .group_by(LinkEvent.group_id)).all()}
        views = {gid: n for gid, n in s.execute(
            select(MediaEvent.group_id, func.count())
            .where(MediaEvent.campaign_id == campaign_id)
            .group_by(MediaEvent.group_id)).all()}
        inter = {gid: n for gid, n in s.execute(
            select(Interaction.group_id, func.count())
            .where(Interaction.campaign_id == campaign_id)
            .group_by(Interaction.group_id)).all()}
    return [{
        "group_id": g, "group": name, "category": cat, "members": mc,
        "status": st, "member_reads": rc, "error_code": ec, "error": et,
        "attempts": att, "clicks": clicks.get(g, 0), "media_views": views.get(g, 0),
        "interactions": inter.get(g, 0),
    } for g, name, cat, mc, st, rc, ec, et, att in rows]


def date_summary(days: int = 30) -> list[dict]:
    since = utcnow() - dt.timedelta(days=days)
    with SessionLocal() as s:
        rows = list(s.execute(
            select(func.date(Campaign.created_at), func.count(),
                   func.coalesce(func.sum(Campaign.target_count), 0))
            .where(Campaign.created_at >= since, Campaign.status != "draft")
            .group_by(func.date(Campaign.created_at))
            .order_by(func.date(Campaign.created_at))).all())
    return [{"date": str(d), "campaigns": c, "targets": int(t)} for d, c, t in rows]
