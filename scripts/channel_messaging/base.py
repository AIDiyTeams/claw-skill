#!/usr/bin/env python3
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SendResult:
    channel: str
    message_id: str
    receive_id_type: str
    images_resolved: bool


class ChannelMessenger(ABC):
    channel: str = ""

    @abstractmethod
    def send_markdown(
        self,
        markdown: str,
        receive_id: str,
        receive_id_type: str,
        mode: str,
    ) -> SendResult:
        raise NotImplementedError
