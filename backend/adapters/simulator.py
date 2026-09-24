# -*- coding: utf-8 -*-
"""Deterministic despatch simulator.

This is the default adapter and the one that makes the proof of concept
runnable without a WhatsApp account. It does NOT send anything. It models the
outcome distribution that the Week 1 proof of concept would measure for real,
so that the queue, the rate governor, the retry path, the analytics pipeline
and the interval snapshot engine can all be exercised end to end.

Error codes are taken from the WhatsApp Cloud API error reference so that the
failure handling built here is the failure handling that will be needed
against the real channel.
"""
import asyncio
import hashlib
import random

import config
from .base import SendResult, GroupRef

# Representative Cloud API errors. Transient entries are worth retrying,
# permanent ones are not. This distinction is what the retry policy consumes.
ERRORS_TRANSIENT = [
    (131026, "Message undeliverable",
     "Unable to deliver the message. Retry may succeed."),
    (131000, "Something went wrong",
     "An unknown error occurred on the platform side."),
    (130429, "Rate limit hit",
     "The message throughput limit for this number was exceeded."),
    (131056, "Pair rate limit hit",
     "Too many messages sent to this destination in a short period."),
]
ERRORS_PERMANENT = [
    (131049, "Not delivered to maintain healthy ecosystem engagement",
     "WhatsApp chose not to deliver this message to protect user experience."),
    (131047, "Re-engagement message required",
     "More than 24 hours have passed since the recipient last replied."),
    (131051, "Unsupported message type",
     "The message type is not supported for this destination."),
    (133010, "Destination not registered",
     "The destination is not a registered WhatsApp destination."),
]


class SimulatorAdapter:
    key = "simulator"
    label = "Despatch simulator (no WhatsApp account required)"
    can_address_existing_groups = True   # within the simulation only
    asynchronous_status = False

    def __init__(self, seed: int | None = None):
        self._seed = seed

    def _rng(self, wa_group_id: str) -> random.Random:
        """Seeded per group so a re-run of the same campaign reproduces the
        same outcomes. Reproducibility matters when the point of the exercise
        is to compare runs."""
        h = hashlib.sha256(f"{self._seed}|{wa_group_id}".encode()).hexdigest()
        return random.Random(int(h[:16], 16))

    async def health(self) -> dict:
        return {
            "adapter": self.key,
            "label": self.label,
            "ready": True,
            "sends_real_messages": False,
            "notes": [
                "No message leaves this machine.",
                "Outcome rates are assumptions from config, not observations.",
                f"Modelled failure rate {config.SIM_FAILURE_RATE:.1%}, "
                f"read rate {config.SIM_READ_PROBABILITY:.0%}.",
            ],
        }

    async def list_groups(self) -> list[GroupRef]:
        return []

    async def send(self, *, wa_group_id: str, body: str,
                   media_path: str | None = None, media_mime: str | None = None,
                   media_caption: str | None = None) -> SendResult:
        rng = self._rng(wa_group_id)
        # Model the cost of a network round trip so the rate governor and the
        # worker pool are genuinely exercised.
        await asyncio.sleep(rng.uniform(0.004, 0.02))

        if rng.random() < config.SIM_FAILURE_RATE:
            transient = rng.random() < config.SIM_TRANSIENT_SHARE
            pool = ERRORS_TRANSIENT if transient else ERRORS_PERMANENT
            code, title, detail = pool[rng.randrange(len(pool))]
            return SendResult(
                ok=False, status="failed", error_code=code, error_title=title,
                error_detail=detail, retryable=transient)

        mid = "wamid.SIM" + hashlib.sha1(
            f"{self._seed}|{wa_group_id}|{body[:40]}".encode()).hexdigest()[:24].upper()

        lo, hi = config.SIM_DELIVER_MS
        delivered_ms = rng.randint(lo, hi)
        read_ms = None
        if rng.random() < config.SIM_READ_PROBABILITY:
            # Reads arrive on a long tail, which is what makes the 15m/1h/3h/8h
            # snapshots show a curve rather than four identical numbers.
            read_ms = delivered_ms + int(rng.lognormvariate(8.6, 1.25) * 1000)

        return SendResult(
            ok=True, provider_message_id=mid, status="sent",
            eventual_status="delivered", delivered_after_ms=delivered_ms,
            read_after_ms=read_ms)
