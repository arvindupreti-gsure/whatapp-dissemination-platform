# -*- coding: utf-8 -*-
"""Official WhatsApp Business Platform adapter (Cloud API + Groups API).

These are real HTTP calls to graph.facebook.com. Supply credentials through
the environment and this adapter will genuinely send.

Read this before enabling it. The official Groups API can only address groups
that it created itself. Per Meta's published limits a group is capped at
8 participants (the business number occupies one slot), a maximum of 10,000
groups may be created per business number, and there is no endpoint to add a
participant: people join by accepting an invite link. Existing WhatsApp groups
cannot be imported. That is why this adapter cannot serve a network of
pre-existing community groups, and why can_address_existing_groups is False.

Status vocabulary comes back through the webhook at /webhooks/whatsapp:
sent, delivered, read, failed, played.
"""
import httpx

import config
from .base import SendResult, GroupRef

GROUP_PARTICIPANT_LIMIT = 8
GROUP_COUNT_LIMIT = 10_000


class CloudApiAdapter:
    key = "cloud_api"
    label = "WhatsApp Business Platform: Cloud API and Groups API (official)"
    can_address_existing_groups = False
    asynchronous_status = True          # terminal state arrives by webhook

    def __init__(self):
        self.base = config.CLOUD_API_BASE
        self.phone_number_id = config.CLOUD_PHONE_NUMBER_ID
        self.waba_id = config.CLOUD_WABA_ID
        self.token = config.CLOUD_ACCESS_TOKEN

    @property
    def configured(self) -> bool:
        return bool(self.phone_number_id and self.token)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"}

    async def health(self) -> dict:
        info = {
            "adapter": self.key,
            "label": self.label,
            "ready": self.configured,
            "sends_real_messages": True,
            "graph_version": config.CLOUD_API_VERSION,
            "phone_number_id_set": bool(self.phone_number_id),
            "waba_id_set": bool(self.waba_id),
            "token_set": bool(self.token),
            "constraints": [
                f"Groups created through this API are capped at "
                f"{GROUP_PARTICIPANT_LIMIT} participants including the business number.",
                f"A maximum of {GROUP_COUNT_LIMIT:,} groups may be created per "
                f"business number.",
                "Existing WhatsApp groups cannot be imported, connected or adopted.",
                "There is no endpoint to add a participant; members join by invite link.",
                "An Official Business Account is required.",
            ],
            "notes": [],
        }
        if not self.configured:
            info["notes"].append(
                "Set WDAP_PHONE_NUMBER_ID and WDAP_ACCESS_TOKEN to enable.")
            return info
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{self.base}/{self.phone_number_id}",
                                headers=self._headers(),
                                params={"fields": "display_phone_number,verified_name,quality_rating"})
            if r.status_code == 200:
                info["phone_number"] = r.json()
                info["reachable"] = True
            else:
                info["reachable"] = False
                info["notes"].append(f"Graph API returned {r.status_code}: {r.text[:300]}")
        except Exception as exc:
            info["reachable"] = False
            info["notes"].append(f"Could not reach the Graph API: {exc}")
        return info

    async def list_groups(self) -> list[GroupRef]:
        """Lists groups this business number created. It cannot see the
        client's pre-existing groups: no such endpoint exists."""
        if not self.configured:
            return []
        out: list[GroupRef] = []
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.get(f"{self.base}/{self.phone_number_id}/groups",
                                headers=self._headers())
            if r.status_code == 200:
                for item in r.json().get("data", []):
                    out.append(GroupRef(
                        wa_group_id=item.get("id", ""),
                        name=item.get("subject", "Untitled group"),
                        member_count=len(item.get("participants", []) or []),
                        source="cloud_api"))
        except Exception:
            pass
        return out

    async def create_group(self, subject: str, description: str = "") -> dict:
        """POST /<PHONE_NUMBER_ID>/groups. Returns the group id and the invite
        link participants must accept to join."""
        if not self.configured:
            raise RuntimeError("Cloud API adapter is not configured")
        payload = {"subject": subject}
        if description:
            payload["description"] = description
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{self.base}/{self.phone_number_id}/groups",
                             headers=self._headers(), json=payload)
        r.raise_for_status()
        return r.json()

    async def send(self, *, wa_group_id: str, body: str,
                   media_path: str | None = None, media_mime: str | None = None,
                   media_caption: str | None = None) -> SendResult:
        if not self.configured:
            return SendResult(ok=False, status="failed", error_code=0,
                              error_title="Adapter not configured",
                              error_detail="Cloud API credentials are absent.",
                              retryable=False)

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "group",       # documented value for group sends
            "to": wa_group_id,               # group id from the Groups API
            "type": "text",
            "text": {"preview_url": True, "body": body},
        }
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(f"{self.base}/{self.phone_number_id}/messages",
                                 headers=self._headers(), json=payload)
            data = r.json() if r.content else {}
        except Exception as exc:
            return SendResult(ok=False, status="failed", error_code=None,
                              error_title="Transport error",
                              error_detail=str(exc)[:400], retryable=True)

        if r.status_code == 200 and data.get("messages"):
            return SendResult(ok=True, status="sent",
                              provider_message_id=data["messages"][0].get("id", ""))

        err = (data.get("error") or {})
        code = err.get("code")
        # 130429 and 131026 are throughput or transient delivery conditions.
        retryable = code in (130429, 131026, 131000, 131056) or r.status_code >= 500
        return SendResult(
            ok=False, status="failed", error_code=code,
            error_title=err.get("message", f"HTTP {r.status_code}")[:280],
            error_detail=((err.get("error_data") or {}).get("details")
                          or r.text)[:400],
            retryable=retryable)
