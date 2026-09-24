# -*- coding: utf-8 -*-
"""The channel abstraction described in Section 5.3 of the proposal.

Campaign creation, group management, analytics and reporting never talk to
WhatsApp directly. They talk to a ChannelAdapter. That is what lets the Week 1
proof of concept swap the despatch mechanism without disturbing the rest of
the build, and what lets the official Cloud API sit alongside the linked
device route later.

Every adapter reports into the same vocabulary as the WhatsApp status webhook:
    sent      the message left our servers
    delivered it reached the recipient device
    read      it was displayed in an open chat thread
    failed    it could not be sent or delivered, with a numeric error code
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class SendResult:
    ok: bool
    provider_message_id: str = ""
    status: str = "sent"           # sent | failed
    error_code: int | None = None
    error_title: str = ""
    error_detail: str = ""
    # Adapters that learn the terminal state synchronously (the simulator)
    # may pre-declare it; webhook driven adapters leave these None.
    eventual_status: str | None = None
    delivered_after_ms: int | None = None
    read_after_ms: int | None = None
    retryable: bool = False
    extra: dict = field(default_factory=dict)


@dataclass
class GroupRef:
    wa_group_id: str
    name: str
    member_count: int = 0
    source: str = "adapter"


class ChannelAdapter(Protocol):
    key: str
    label: str
    # Whether this adapter can address the client's pre-existing groups.
    can_address_existing_groups: bool
    # Whether terminal delivery state arrives later via webhook or poll.
    asynchronous_status: bool

    async def health(self) -> dict:
        """Report readiness and configuration without leaking secrets."""

    async def list_groups(self) -> list[GroupRef]:
        """Enumerate groups visible to this channel, where supported."""

    async def send(self, *, wa_group_id: str, body: str,
                   media_path: str | None, media_mime: str | None,
                   media_caption: str | None) -> SendResult:
        """Despatch one message to one group."""


class AdapterError(RuntimeError):
    pass
