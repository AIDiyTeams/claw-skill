#!/usr/bin/env python3
from __future__ import annotations

from channel_messaging.base import ChannelMessenger
from channel_messaging.feishu import FeishuMessenger


def get_channel_messenger(channel: str) -> ChannelMessenger:
    normalized = (channel or "").strip().lower()
    if normalized == "feishu":
        return FeishuMessenger()
    raise ValueError(f"Unsupported channel '{channel}'. Supported: feishu")
