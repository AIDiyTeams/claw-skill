---
name: custom-gift-leewow
description: >-
  Browse and create custom gifts — personalized bags, mugs, phone cases,
  apparel and more. Upload any image to generate an AI-powered product mockup.
  Includes two tools: browse_templates (discover products) and generate_preview
  (create a design from an image). Powered by Leewow.
  Requires a Leewow Secret Key (CLAW_SK). If not configured, guide the user
  to obtain one at https://leewow.com/profile/secret-keys and set it via
  environment variable. When the user provides their SK, save it to CLAW_SK.
---

# Custom Gift — Leewow

Create personalized gifts and custom products powered by AI. This skill provides two core capabilities:

| Tool | Purpose |
|------|---------|
| `browse_templates` | Discover customizable product templates (bags, accessories, home decor, apparel, etc.) |
| `generate_preview` | Upload a design image and generate a product mockup with AI |

## When to Use

- User wants to **send a gift** or **create something personalized**
- User says "browse products", "show me what I can customize", "gift ideas"
- User provides an **image** and wants to turn it into a product
- User says "make this into a mug/bag/shirt", "customize this design", "create a gift from this photo"

## Prerequisites

- `CLAW_SK` — Leewow Secret Key (format: `sk-leewow-{keyId}-{secret}`)
- `CLAW_BASE_URL` — API base URL (default: `https://leewow.com`)
- `CLAW_PATH_PREFIX` — Path prefix for reverse proxy (default: empty; set `/v2` if needed)
- `LEEWOW_API_BASE` — Base URL for COS STS credentials (default: `https://leewow.com`)
- Python 3.10+ with `requests` and `cos-python-sdk-v5`

## Instructions

### First-Time Setup (SK Configuration)

Before first use, check whether `CLAW_SK` is set. If any tool returns an error
containing "CLAW_SK", follow this flow:

1. Ask the user: "To use Leewow gift features, I need your Secret Key (SK). You can create one at https://leewow.com/profile/secret-keys — do you have one?"
2. If the user provides an SK (format: `sk-leewow-{keyId}-{secret}`), save it to the `CLAW_SK` environment variable.
3. If the user says they don't have one, direct them to https://leewow.com/profile/secret-keys to create a new key, then wait for them to provide it.

### Typical Flow

1. **Browse first** — Use `browse_templates` to show the user available products. Each card includes a Template ID.
2. **Generate** — Once the user picks a template and provides an image, use `generate_preview` to create a personalized mockup.
3. **Share the result** — The preview link lets the user view the AI-generated design, pick sizes, and place an order.

### Using `browse_templates`

- Call with optional `category` (bag / accessory / home / apparel) and `count` (1–5).
- Returns Markdown cards with product images, names, pricing, and template IDs.

### Using `generate_preview`

- Requires `image_path` (local file) and `template_id` (from browse results).
- Optional: `design_theme` (style description) and `aspect_ratio` (3:4 / 1:1 / 4:3).
- The tool uploads the image, triggers async AI generation (~30–60 seconds), and returns a preview URL.

## Safety Rules

- Never expose or log the `CLAW_SK` value. When confirming configuration, only show the last 4 characters (e.g. `sk-leewow-****-****a1b2`).
- Limit browse results to 5 templates maximum per request.
- Validate that the image file exists before calling `generate_preview`.
- Inform the user that generation is asynchronous and takes about 30–60 seconds.

## Examples

```text
User: "I want to make a custom gift for my friend"
→ Use browse_templates to show options, then generate_preview after user picks a template and provides an image.

User: "Turn this photo into a phone case"
→ Use browse_templates with relevant category, let user pick, then generate_preview.

User: "Show me what products I can customize"
→ Use browse_templates.

User: "Here's my design, put it on template #7"
→ Use generate_preview directly.
```
