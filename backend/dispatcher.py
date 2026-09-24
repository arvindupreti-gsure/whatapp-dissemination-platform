# -*- coding: utf-8 -*-
"""Despatch engine.

Implements Section 5.3 of the proposal:
  - every campaign is expanded into individual per group jobs in a durable
    queue, so a campaign can be paused, resumed, throttled or partially
    retried without being resent in full
  - a rate governor paces sending with randomised intervals, a daily ceiling
    and a staged warm up profile
  - transient failures are retried with backoff, permanent ones are not
  - the outcome of every individual group send is written back against the
    campaign record

Delivery maturation (sent -> delivered -> read) is driven by a single time
ordered heap rather than a task per message, so 5,000 groups costs one
background loop rather than 10,000 coroutines.
"""
import asyncio
import datetime as dt
import heapq
import random
import secrets
import time

from sqlalchemy import select, update, func

import adapters
import config
from db import (SessionLocal, Campaign, Delivery, Group, EventLog, TrackedLink,
                LinkEvent, Interaction, MediaEvent, utcnow)

# ------------------------------------------------------------------ state
_queues: dict[int, asyncio.Queue] = {}
_control: dict[int, str] = {}          # campaign_id -> running | paused | cancelled
_workers: dict[int, list] = {}
_maturation: list = []                 # heap of (due_monotonic, seq, event)
_mat_seq = 0
_mat_event = asyncio.Event()
_sent_today = 0
_day_stamp = dt.date.today()
_loop_started = False


def log(campaign_id: int | None, message: str, level: str = "info"):
    with SessionLocal() as s:
        s.add(EventLog(campaign_id=campaign_id, level=level, message=message))
        s.commit()


def _check_daily_ceiling(n: int = 1) -> bool:
    global _sent_today, _day_stamp
    today = dt.date.today()
    if today != _day_stamp:
        _day_stamp, _sent_today = today, 0
    if _sent_today + n > config.DAILY_CEILING:
        return False
    _sent_today += n
    return True


def daily_usage() -> dict:
    return {"sent_today": _sent_today, "ceiling": config.DAILY_CEILING}


# ------------------------------------------------------------ rate governor
class RateGovernor:
    """Token bucket with randomised inter message spacing and a warm up ramp.

    The warm up matters: a number that has never sent in volume should not
    begin at full rate. The ramp reaches full rate over the first 500 sends.
    """

    def __init__(self, rate_per_sec: float, jitter: float, warmup_over: int = 500):
        self.rate = max(0.5, rate_per_sec)
        self.jitter = max(0.0, min(0.9, jitter))
        self.warmup_over = max(1, warmup_over)
        self._count = 0
        self._next_at = time.monotonic()
        self._lock = asyncio.Lock()

    def _current_rate(self) -> float:
        ramp = min(1.0, 0.15 + 0.85 * (self._count / self.warmup_over))
        return self.rate * ramp

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            interval = 1.0 / self._current_rate()
            interval *= random.uniform(1 - self.jitter, 1 + self.jitter)
            self._next_at = max(now, self._next_at) + interval
            wait = self._next_at - now
            self._count += 1
        if wait > 0:
            await asyncio.sleep(wait)


_governor = RateGovernor(config.SEND_RATE_PER_SEC, config.SEND_JITTER_PCT)


def governor_state() -> dict:
    return {"rate_per_sec": _governor.rate, "jitter": _governor.jitter,
            "effective_rate": round(_governor._current_rate(), 2),
            "sends_this_process": _governor._count}


def set_rate(rate: float, jitter: float):
    _governor.rate = max(0.5, float(rate))
    _governor.jitter = max(0.0, min(0.9, float(jitter)))


# --------------------------------------------------------------- maturation
def _schedule(delay_sec: float, event: dict):
    global _mat_seq
    _mat_seq += 1
    heapq.heappush(_maturation, (time.monotonic() + max(0.0, delay_sec),
                                 _mat_seq, event))
    _mat_event.set()


async def maturation_loop():
    """Applies delivered / read / click / reply transitions when they fall
    due. One loop for the whole platform."""
    while True:
        if not _maturation:
            _mat_event.clear()
            try:
                await asyncio.wait_for(_mat_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            continue
        due_at = _maturation[0][0]
        now = time.monotonic()
        if due_at > now:
            await asyncio.sleep(min(0.25, due_at - now))
            continue

        batch = []
        while _maturation and _maturation[0][0] <= time.monotonic() and len(batch) < 500:
            batch.append(heapq.heappop(_maturation)[2])
        if batch:
            try:
                _apply_batch(batch)
            except Exception as exc:                      # pragma: no cover
                log(None, f"maturation error: {exc}", "error")
        await asyncio.sleep(0)


def _apply_batch(batch: list[dict]):
    with SessionLocal() as s:
        for ev in batch:
            kind = ev["kind"]
            if kind == "delivered":
                d = s.get(Delivery, ev["delivery_id"])
                if d and d.status == "sent":
                    d.status = "delivered"
                    d.delivered_at = utcnow()
            elif kind == "read":
                d = s.get(Delivery, ev["delivery_id"])
                if d and d.status in ("sent", "delivered"):
                    d.status = "read"
                    d.read_at = utcnow()
                    # Group read receipts are reported in aggregate, not per
                    # participant. read_count models how many members read.
                    d.read_count = ev.get("read_count", 1)
            elif kind == "click":
                link = s.get(TrackedLink, ev["link_id"])
                if link:
                    link.clicks += 1
                    link.unique_clicks += 1
                    s.add(LinkEvent(link_id=link.id, campaign_id=link.campaign_id,
                                    group_id=link.group_id,
                                    visitor_hash=secrets.token_hex(8),
                                    user_agent="simulated"))
            elif kind == "media_view":
                s.add(MediaEvent(media_id=ev["media_id"],
                                 campaign_id=ev["campaign_id"],
                                 group_id=ev["group_id"], kind="view"))
            elif kind == "interaction":
                s.add(Interaction(campaign_id=ev["campaign_id"],
                                  group_id=ev["group_id"], kind=ev["subkind"],
                                  text=ev.get("text", "")))
            elif kind == "snapshot":
                from analytics import take_snapshot
                take_snapshot(ev["campaign_id"], ev["label"], session=s)
        s.commit()


# ------------------------------------------------------------------ helpers
def _make_tracked_links(campaign: Campaign, group_ids: list[int]) -> dict[int, str]:
    """One short link per (campaign, group). This is what makes click data
    attributable to an individual group."""
    if not campaign.link_url:
        return {}
    out = {}
    with SessionLocal() as s:
        existing = {t.group_id: t for t in s.scalars(
            select(TrackedLink).where(TrackedLink.campaign_id == campaign.id))}
        for gid in group_ids:
            t = existing.get(gid)
            if t is None:
                t = TrackedLink(token=secrets.token_urlsafe(8)[:10],
                                campaign_id=campaign.id, group_id=gid,
                                target_url=campaign.link_url)
                s.add(t)
            out[gid] = t.token
        s.commit()
        for gid, tok in list(out.items()):
            out[gid] = tok if isinstance(tok, str) else tok.token
    return out


def render_body(campaign: Campaign, group: Group, token: str | None,
                media_token: str | None = None) -> str:
    body = campaign.body or ""
    body = body.replace("{{group_name}}", group.name)
    body = body.replace("{{campaign_name}}", campaign.name)
    if token:
        short = f"{config.PUBLIC_BASE_URL}/t/{token}"
        body = body.replace("{{link}}", short)
        if "{{link}}" not in (campaign.body or "") and campaign.link_url:
            body = f"{body}\n{short}"
    if media_token:
        body = f"{body}\n{config.PUBLIC_BASE_URL}/m/{media_token}"
    return body


# ------------------------------------------------------------------- engine
async def _worker(campaign_id: int, channel: str, seed: int, q: asyncio.Queue):
    adapter = adapters.get(channel, seed=seed)
    while True:
        item = await q.get()
        if item is None:
            q.task_done()
            return
        if _control.get(campaign_id) == "cancelled":
            q.task_done()
            continue
        while _control.get(campaign_id) == "paused":
            await asyncio.sleep(0.4)
            if _control.get(campaign_id) == "cancelled":
                q.task_done()
                break
        else:
            try:
                await _send_one(adapter, campaign_id, item)
            except Exception as exc:                       # pragma: no cover
                log(campaign_id, f"worker error on group {item.get('group_id')}: {exc}",
                    "error")
            finally:
                q.task_done()
            continue
        # reached only if cancelled while paused
        continue


async def _send_one(adapter, campaign_id: int, job: dict):
    if not _check_daily_ceiling():
        log(campaign_id, "Daily send ceiling reached. Remaining jobs deferred.",
            "warn")
        await asyncio.sleep(1.0)
        return

    await _governor.acquire()

    res = await adapter.send(
        wa_group_id=job["wa_group_id"], body=job["body"],
        media_path=job.get("media_path"), media_mime=job.get("media_mime"),
        media_caption=job.get("media_caption"))

    now = utcnow()
    with SessionLocal() as s:
        d = s.get(Delivery, job["delivery_id"])
        if d is None:
            return
        d.attempts += 1
        if res.ok:
            d.status = "sent"
            d.sent_at = now
            d.provider_message_id = res.provider_message_id
            d.error_code, d.error_title, d.error_detail = None, "", ""
            s.commit()
            _schedule_maturation(d.id, job, res)
        else:
            d.error_code = res.error_code
            d.error_title = res.error_title
            d.error_detail = res.error_detail
            if res.retryable and d.attempts < config.MAX_ATTEMPTS:
                d.status = "queued"
                s.commit()
                delay = config.RETRY_BACKOFF_SEC * (2 ** (d.attempts - 1))
                log(campaign_id,
                    f"Retry {d.attempts}/{config.MAX_ATTEMPTS} for "
                    f"{job['group_name']} in {delay:.0f}s: {res.error_title}", "warn")
                await asyncio.sleep(0)
                asyncio.create_task(_requeue(campaign_id, job, delay))
            else:
                d.status = "failed"
                s.commit()


async def _requeue(campaign_id: int, job: dict, delay: float):
    await asyncio.sleep(delay)
    q = _queues.get(campaign_id)
    if q is not None and _control.get(campaign_id) not in ("cancelled",):
        await q.put(job)


def _schedule_maturation(delivery_id: int, job: dict, res):
    """Queue the delivered / read / click / interaction transitions."""
    if res.delivered_after_ms is None:
        return                                  # webhook driven adapter
    scale = config.TIME_SCALE
    d_delay = (res.delivered_after_ms / 1000.0) * scale
    _schedule(d_delay, {"kind": "delivered", "delivery_id": delivery_id})

    if res.read_after_ms is None:
        return
    r_delay = (res.read_after_ms / 1000.0) * scale
    rng = random.Random(delivery_id)
    members = max(1, job.get("member_count", 1))
    read_count = max(1, int(members * rng.uniform(0.25, 0.85)))
    _schedule(r_delay, {"kind": "read", "delivery_id": delivery_id,
                        "read_count": read_count})

    cid, gid = job["campaign_id"], job["group_id"]
    if job.get("link_id") and rng.random() < config.SIM_CLICK_OF_READ:
        for _ in range(rng.randint(1, 3)):
            _schedule(r_delay + rng.uniform(1, 600) * scale,
                      {"kind": "click", "link_id": job["link_id"]})
    if job.get("media_id") and rng.random() < config.SIM_CLICK_OF_READ * 1.4:
        _schedule(r_delay + rng.uniform(1, 400) * scale,
                  {"kind": "media_view", "media_id": job["media_id"],
                   "campaign_id": cid, "group_id": gid})
    if rng.random() < config.SIM_REPLY_OF_READ:
        _schedule(r_delay + rng.uniform(5, 900) * scale,
                  {"kind": "interaction", "campaign_id": cid, "group_id": gid,
                   "subkind": "reply", "text": "Acknowledged, thank you."})
    if rng.random() < config.SIM_OPTOUT_OF_READ:
        _schedule(r_delay + rng.uniform(5, 900) * scale,
                  {"kind": "interaction", "campaign_id": cid, "group_id": gid,
                   "subkind": "optout", "text": "STOP"})


# ------------------------------------------------------------------- public
async def launch(campaign_id: int):
    """Expand a campaign into per group jobs and start the worker pool."""
    global _loop_started
    if not _loop_started:
        asyncio.create_task(maturation_loop())
        asyncio.create_task(_completion_loop())
        _loop_started = True

    with SessionLocal() as s:
        camp = s.get(Campaign, campaign_id)
        if camp is None:
            raise ValueError("Campaign not found")
        if camp.status == "running":
            return
        deliveries = list(s.scalars(
            select(Delivery).where(Delivery.campaign_id == campaign_id)))
        if not deliveries:
            raise ValueError("Campaign has no targets")
        gids = [d.group_id for d in deliveries]
        groups = {g.id: g for g in s.scalars(
            select(Group).where(Group.id.in_(gids)))}
        camp.status = "running"
        camp.started_at = utcnow()
        s.commit()
        channel, seed = camp.channel, camp.id
        media = camp.media
        media_path = media.stored_path if media else None
        media_mime = media.mime if media else None
        media_id = media.id if media and media.tracked else None
        camp_snapshot = camp

    tokens = _make_tracked_links(camp_snapshot, gids)
    link_ids = {}
    if tokens:
        with SessionLocal() as s:
            for t in s.scalars(select(TrackedLink).where(
                    TrackedLink.campaign_id == campaign_id)):
                link_ids[t.group_id] = t.id

    q: asyncio.Queue = asyncio.Queue()
    _queues[campaign_id] = q
    _control[campaign_id] = "running"

    pending = [d for d in deliveries if d.status in ("queued", "failed")]
    for d in pending:
        g = groups.get(d.group_id)
        if g is None:
            continue
        mtok = None
        if media_id:
            from tokens import make_media_token
            mtok = make_media_token(campaign_id, g.id, media_id)
        body = render_body(camp_snapshot, g, tokens.get(g.id), mtok)
        await q.put({
            "delivery_id": d.id, "campaign_id": campaign_id, "group_id": g.id,
            "wa_group_id": g.wa_group_id, "group_name": g.name,
            "member_count": g.member_count, "body": body,
            "media_path": media_path, "media_mime": media_mime,
            "media_caption": camp_snapshot.name, "media_id": media_id,
            "link_id": link_ids.get(g.id),
        })

    workers = [asyncio.create_task(_worker(campaign_id, channel, seed, q))
               for _ in range(config.WORKER_COUNT)]
    _workers[campaign_id] = workers
    log(campaign_id,
        f"Campaign started on channel '{channel}' with {len(pending)} targets, "
        f"{config.WORKER_COUNT} workers at {_governor.rate:.0f} msg/s nominal.")


def pause(campaign_id: int):
    _control[campaign_id] = "paused"
    with SessionLocal() as s:
        c = s.get(Campaign, campaign_id)
        if c and c.status == "running":
            c.status = "paused"
            s.commit()
    log(campaign_id, "Campaign paused by operator.", "warn")


def resume(campaign_id: int):
    _control[campaign_id] = "running"
    with SessionLocal() as s:
        c = s.get(Campaign, campaign_id)
        if c and c.status == "paused":
            c.status = "running"
            s.commit()
    log(campaign_id, "Campaign resumed by operator.")


def cancel(campaign_id: int):
    _control[campaign_id] = "cancelled"
    with SessionLocal() as s:
        c = s.get(Campaign, campaign_id)
        if c:
            c.status = "cancelled"
            c.completed_at = utcnow()
            s.commit()
    log(campaign_id, "Campaign cancelled by operator.", "warn")


async def _completion_loop():
    """Detects campaigns whose queue has drained and closes them out."""
    while True:
        await asyncio.sleep(1.0)
        for cid in list(_queues.keys()):
            if _control.get(cid) in ("cancelled",):
                _queues.pop(cid, None)
                continue
            with SessionLocal() as s:
                camp = s.get(Campaign, cid)
                if camp is None or camp.status not in ("running", "paused"):
                    continue
                rows = s.execute(
                    select(Delivery.status, func.count())
                    .where(Delivery.campaign_id == cid)
                    .group_by(Delivery.status)).all()
                counts = {k: v for k, v in rows}
                outstanding = counts.get("queued", 0)
                if outstanding or camp.status == "paused":
                    continue
                failed = counts.get("failed", 0)
                camp.status = "partially_failed" if failed else "completed"
                camp.completed_at = utcnow()
                s.commit()
                total = sum(counts.values())
                log(cid, f"Despatch complete. {total - failed}/{total} groups "
                         f"reached, {failed} failed. Interval snapshots scheduled.")
            _finish(cid)


def _finish(campaign_id: int):
    q = _queues.pop(campaign_id, None)
    for t in _workers.pop(campaign_id, []):
        t.cancel()
    for label, seconds in config.SNAPSHOT_INTERVALS:
        _schedule(config.scaled(seconds),
                  {"kind": "snapshot", "campaign_id": campaign_id, "label": label})


def runtime_state(campaign_id: int) -> dict:
    return {"control": _control.get(campaign_id, "idle"),
            "queued_in_memory": _queues[campaign_id].qsize()
            if campaign_id in _queues else 0,
            "governor": governor_state(), "daily": daily_usage()}
