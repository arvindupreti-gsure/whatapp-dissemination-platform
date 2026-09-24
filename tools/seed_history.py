# -*- coding: utf-8 -*-
"""Seed a realistic campaign history so the dashboard trend lines have shape.

Demonstration data only. Every campaign it creates runs on the SIMULATOR
channel and targets only the seeded groups, never the live linked-device
groups, so nothing here implies a real WhatsApp message was ever sent.

    python tools/seed_history.py            # create 30 days of history
    python tools/seed_history.py --days 45  # a longer run-up
    python tools/seed_history.py --undo     # remove exactly what it created

The ids it creates are recorded in tools/.seeded_campaigns.json so --undo
removes those rows and nothing else.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select, func, delete          # noqa: E402
from db import SessionLocal, Campaign, Delivery, Group, utcnow  # noqa: E402

LEDGER = Path(__file__).resolve().parent / ".seeded_campaigns.json"

NAMES = [
    "Weekly community bulletin", "Scheme awareness drive", "Monsoon advisory",
    "Health camp notice", "Public grievance update", "Skill programme enrolment",
    "Ration distribution notice", "Vaccination drive reminder",
    "Local body announcement", "Farmer advisory", "Scholarship deadline reminder",
    "Employment mela notice", "Water supply advisory", "Civic maintenance notice",
    "Festival safety advisory", "Survey participation request",
    "Pension disbursement notice", "School enrolment drive",
    "Electricity maintenance notice", "Disaster preparedness advisory",
]


def next_code(s) -> int:
    last = s.scalar(select(func.max(Campaign.id))) or 0
    return last + 1


def seed(days: int, seed_value: int) -> None:
    rng = random.Random(seed_value)
    today = utcnow().date()

    with SessionLocal() as s:
        pool = [g.id for g in s.scalars(
            select(Group).where(Group.source == "seed").limit(5000))]
        if not pool:
            print("No seeded groups found. Nothing to target; aborting.")
            return
        print(f"Targeting a pool of {len(pool):,} demonstration groups.")

        created: list[int] = []
        rows: list[dict] = []
        name_i = 0

        for back in range(days - 1, -1, -1):
            day = today - dt.timedelta(days=back)
            # Sundays are quiet, and roughly one weekday in six has no campaign
            if day.weekday() == 6 or rng.random() < 0.16:
                continue

            # gentle upward trend across the window, plus day to day noise
            progress = (days - back) / days
            base = 850 + 1500 * progress
            targets = int(base * rng.uniform(0.72, 1.28))
            targets = max(320, min(len(pool), targets))

            hour = rng.choice([9, 10, 11, 14, 15, 16])
            start = dt.datetime.combine(day, dt.time(hour, rng.randint(0, 55)))

            cid = next_code(s)
            camp = Campaign(
                id=cid, code=f"CMP-{cid:05d}", name=NAMES[name_i % len(NAMES)],
                body="Demonstration campaign seeded for dashboard history.",
                status="completed", channel="simulator",
                created_at=start, started_at=start,
                completed_at=start + dt.timedelta(minutes=rng.randint(4, 22)),
                target_count=targets)
            name_i += 1

            # outcome mix: delivery quality improves slightly over the window
            fail_rate = rng.uniform(0.055, 0.015 + 0.03 * (1 - progress))
            pending_rate = rng.uniform(0.004, 0.02)
            read_share = rng.uniform(0.55, 0.78)

            n_failed = int(targets * fail_rate)
            n_pending = int(targets * pending_rate)
            n_ok = targets - n_failed - n_pending
            n_read = int(n_ok * read_share)
            n_delivered = n_ok - n_read

            if n_failed:
                camp.status = "partially_failed"
            s.add(camp)
            s.flush()
            created.append(camp.id)

            chosen = rng.sample(pool, targets)
            i = 0

            def stamp(spread_minutes: int) -> dt.datetime:
                return start + dt.timedelta(
                    seconds=rng.randint(0, spread_minutes * 60))

            for _ in range(n_read):
                sent = stamp(18)
                dl = sent + dt.timedelta(seconds=rng.randint(2, 90))
                rows.append(dict(
                    campaign_id=camp.id, group_id=chosen[i], status="read",
                    attempts=1, provider_message_id=f"sim.{camp.id}.{i}",
                    queued_at=start, sent_at=sent, delivered_at=dl,
                    read_at=dl + dt.timedelta(minutes=rng.randint(1, 240)),
                    read_count=rng.randint(1, 9)))
                i += 1
            for _ in range(n_delivered):
                sent = stamp(18)
                rows.append(dict(
                    campaign_id=camp.id, group_id=chosen[i], status="delivered",
                    attempts=1, provider_message_id=f"sim.{camp.id}.{i}",
                    queued_at=start, sent_at=sent,
                    delivered_at=sent + dt.timedelta(seconds=rng.randint(2, 90)),
                    read_at=None, read_count=0))
                i += 1
            for _ in range(n_failed):
                rows.append(dict(
                    campaign_id=camp.id, group_id=chosen[i], status="failed",
                    attempts=rng.randint(1, 3),
                    provider_message_id="", error_code=131049,
                    error_title="Message not delivered",
                    error_detail="This message was not delivered to maintain "
                                 "healthy ecosystem engagement.",
                    queued_at=start, sent_at=stamp(18)))
                i += 1
            for _ in range(n_pending):
                rows.append(dict(
                    campaign_id=camp.id, group_id=chosen[i], status="sent",
                    attempts=1, provider_message_id=f"sim.{camp.id}.{i}",
                    queued_at=start, sent_at=stamp(18)))
                i += 1

            print(f"  {day}  {camp.code}  {camp.name[:34]:34s} "
                  f"targets={targets:5d}  reached={n_ok:5d}  failed={n_failed:4d}")

        if not created:
            print("Nothing created.")
            return

        s.bulk_insert_mappings(Delivery, rows)
        s.commit()

    prev = json.loads(LEDGER.read_text()) if LEDGER.exists() else []
    LEDGER.write_text(json.dumps(sorted(set(prev) | set(created))))
    print(f"\nCreated {len(created)} campaigns and {len(rows):,} delivery rows.")
    print(f"Ledger written to {LEDGER.name}. Run with --undo to remove them.")


def undo() -> None:
    if not LEDGER.exists():
        print("No ledger found. Nothing was seeded by this tool.")
        return
    ids = json.loads(LEDGER.read_text())
    if not ids:
        print("Ledger is empty.")
        return
    with SessionLocal() as s:
        d = s.execute(delete(Delivery).where(Delivery.campaign_id.in_(ids)))
        c = s.execute(delete(Campaign).where(Campaign.id.in_(ids)))
        s.commit()
    LEDGER.unlink()
    print(f"Removed {c.rowcount} campaigns and {d.rowcount} delivery rows.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260924)
    ap.add_argument("--undo", action="store_true")
    a = ap.parse_args()
    undo() if a.undo else seed(max(7, min(120, a.days)), a.seed)
