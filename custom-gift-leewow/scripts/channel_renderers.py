#!/usr/bin/env python3
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable


def normalize_plain_text(value: object) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def escape_table_cell(value: object) -> str:
    text = normalize_plain_text(value)
    if not text:
        return "-"
    return text.replace("|", "\\|")


def compact_description(value: object, limit: int = 56) -> str:
    text = normalize_plain_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def normalize_browse_item(template: dict, price_display: str) -> dict:
    sku_type = normalize_plain_text(template.get("skuType")) or "-"
    shipping = normalize_plain_text(template.get("shippingOrigin")) or "CN"
    description = compact_description(template.get("description", ""))
    info_parts = [f"SKU: {sku_type}", f"Ships: {shipping}"]
    if description:
        info_parts.append(description)
    return {
        "templateId": template.get("templateId", "?"),
        "name": normalize_plain_text(template.get("name", "Unnamed Product")) or "Unnamed Product",
        "coverImage": normalize_plain_text(template.get("coverImage")),
        "price": price_display or "-",
        "skuType": sku_type,
        "shippingOrigin": shipping,
        "description": description,
        "info": " · ".join(info_parts),
    }


class ChannelRenderer(ABC):
    channel: str = "plain"

    @abstractmethod
    def render_browse(self, items: Iterable[dict]) -> str:
        raise NotImplementedError


class PlainTextRenderer(ChannelRenderer):
    channel = "plain"

    def render_browse(self, items: Iterable[dict]) -> str:
        rows = list(items)
        if not rows:
            return "No matching templates found. Try a different category or browse all."

        lines = [f"Available Product Templates ({len(rows)} results)", ""]
        for index, item in enumerate(rows, 1):
            lines.append(f"{index}. {item['name']}")
            lines.append(f"Template ID: `{item['templateId']}`")
            lines.append(f"Price: {item['price']}")
            lines.append(item["info"])
            if item["coverImage"]:
                lines.append(f"Preview: {item['coverImage']}")
            lines.append("")
        lines.append("Use `generate_preview` with a `Template ID` to create a customized design.")
        return "\n".join(lines)


class FeishuRenderer(ChannelRenderer):
    channel = "feishu"

    def render_browse(self, items: Iterable[dict]) -> str:
        rows = list(items)
        if not rows:
            return "No matching templates found. Try a different category or browse all."

        lines = [
            f"## Available Product Templates ({len(rows)} results)",
            "",
            "| Image | Product | Price | Template ID | Info | Preview |",
            "| --- | --- | --- | --- | --- | --- |",
        ]

        for item in rows:
            image_cell = self._format_image_cell(item["name"], item["coverImage"])
            preview_link = self._format_preview_link(item["coverImage"])
            price_display = str(item["price"]).replace("|", "\\|")
            lines.append(
                "| "
                f"{image_cell} | "
                f"**{escape_table_cell(item['name'])}** | "
                f"{price_display} | "
                f"`{item['templateId']}` | "
                f"{escape_table_cell(item['info'])} | "
                f"{preview_link} |"
            )

        lines.extend(
            [
                "",
                "Reply with the Template ID you want to continue.",
                "Use `generate_preview` with a `Template ID` to create a customized design.",
                "If a thumbnail does not render in Feishu, use the `Preview` link in the same row.",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _format_image_cell(name: str, cover_url: str) -> str:
        if not cover_url:
            return "-"
        return f"![{escape_table_cell(name or 'Preview')}]({cover_url})"

    @staticmethod
    def _format_preview_link(cover_url: str) -> str:
        if not cover_url:
            return "-"
        return f"[Open image]({cover_url})"


_RENDERERS = {
    PlainTextRenderer.channel: PlainTextRenderer(),
    FeishuRenderer.channel: FeishuRenderer(),
}


def get_channel_renderer(channel: str | None) -> ChannelRenderer:
    normalized = normalize_plain_text(channel).lower() or FeishuRenderer.channel
    if normalized not in _RENDERERS:
        supported = ", ".join(sorted(_RENDERERS))
        raise ValueError(f"Unsupported channel '{channel}'. Supported: {supported}")
    return _RENDERERS[normalized]
