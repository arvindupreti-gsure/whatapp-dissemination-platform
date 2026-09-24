# -*- coding: utf-8 -*-
"""Adapter registry. The rest of the platform resolves a channel by key and
never imports a concrete adapter."""
from .base import ChannelAdapter, SendResult, GroupRef, AdapterError
from .simulator import SimulatorAdapter
from .cloud_api import CloudApiAdapter
from .linked_device import LinkedDeviceAdapter

_REGISTRY = {}


def get(key: str, seed: int | None = None):
    key = (key or "simulator").lower()
    if key == "simulator":
        # Seeded per campaign so re-running a campaign reproduces outcomes.
        return SimulatorAdapter(seed=seed)
    if key not in _REGISTRY:
        if key == "cloud_api":
            _REGISTRY[key] = CloudApiAdapter()
        elif key == "linked_device":
            _REGISTRY[key] = LinkedDeviceAdapter()
        else:
            raise AdapterError(f"Unknown channel adapter: {key}")
    return _REGISTRY[key]


def available() -> list[dict]:
    return [
        {"key": "simulator", "label": SimulatorAdapter.label,
         "sends_real_messages": False,
         "can_address_existing_groups": True},
        {"key": "cloud_api", "label": CloudApiAdapter.label,
         "sends_real_messages": True,
         "can_address_existing_groups": False},
        {"key": "linked_device", "label": LinkedDeviceAdapter.label,
         "sends_real_messages": True,
         "can_address_existing_groups": True},
    ]


__all__ = ["get", "available", "ChannelAdapter", "SendResult", "GroupRef",
           "AdapterError"]
