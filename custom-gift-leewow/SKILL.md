---
name: custom-gift-leewow
version: 1.0.12
description: >-
  Browse and create custom gifts — personalized bags, mugs, phone cases,
  apparel and more. Upload any image to generate an AI-powered product mockup.
  Includes tools: browse_templates (discover products), generate_preview
  (create a design from an image), and get_generation_status (check generation
  progress). browse_templates returns per-product markdown messages with a
  customer-facing subtitle and one large image per message. Generated previews
  are still downloaded to workspace for display. Powered by Leewow. Requires
  CLAW_SK. If ClawHub is rate-limited,
  install from GitHub:
  https://github.com/AIDiyTeams/claw-skill/tree/main/custom-gift-leewow
homepage: https://github.com/AIDiyTeams/claw-skill/tree/main/custom-gift-leewow
---

# Custom Gift — Leewow

> ClawHub rate-limited? Install directly from GitHub:
> `https://github.com/AIDiyTeams/claw-skill/tree/main/custom-gift-leewow`

> Feishu browse rule: product browsing MUST be shown as multiple product
> messages. Each message should contain one product title, one customer-facing
> subtitle, and one large image.

## Install Fallback

If ClawHub is rate-limited, install this skill directly from GitHub:

- Repository: `https://github.com/AIDiyTeams/claw-skill`
- Skill path: `custom-gift-leewow`

Manual fallback:

```bash
cd /path/to/your/openclaw-workspace
mkdir -p skills
git clone https://github.com/AIDiyTeams/claw-skill.git /tmp/claw-skill
cp -R /tmp/claw-skill/custom-gift-leewow ./skills/custom-gift-leewow
```

Create personalized gifts and custom products powered by AI. This skill provides:

| Tool | Purpose |
|------|---------|
| `browse_templates` | Discover customizable product templates (bags, accessories, home decor, apparel, etc.) |
| `generate_preview` | Upload a design image and trigger AI generation |
| `get_generation_status` | Check generation status and download preview image |

## When to Use

- User wants to **send a gift** or **create something personalized**
- User says "browse products", "show me what I can customize", "gift ideas"
- User provides an **image** and wants to turn it into a product
- User says "make this into a mug/bag/shirt", "customize this design"

## Browse Output Format

`browse_templates` now returns delivery JSON with `messagesMarkdown`:
- Each `messagesMarkdown` item is one final user-facing Markdown message
- For Feishu, each message shows one product
- Layout goal: bold product name, smaller description underneath, then one large image below
- The agent should send each `messagesMarkdown` item directly, in order, as separate messages

## Priority Rule

For the current production channel (`feishu`):
- `browse_templates` MUST be displayed as multiple product messages, one product per message
- Each browse message MUST keep the product image inside the same message, below the title/description
- For browse requests, the agent MUST send each returned `messagesMarkdown` item verbatim unless the user explicitly asks for another format
- For browse requests, the agent MUST NOT answer with a status summary, tool summary, or explanation of what the browse messages contain
- The agent MUST NOT explain that "the skill does not require a table" because the current skill explicitly defines a per-product browse message layout
- The agent MUST NOT cite the generated-preview media rule as justification for changing the browse layout

Important distinction:
- `browse_templates` = multiple markdown messages, one per product
- `get_generation_status` = generated preview image sent as media attachment, then `replyMarkdown` sent as text

## Verbatim Contract

For `browse_templates`, the returned `messagesMarkdown` array already contains the final user-facing replies.

The next assistant messages after calling `browse_templates` MUST:
- send each `messagesMarkdown` item exactly as returned
- preserve order
- not add any explanation before or after any item
- not summarize, restyle, translate, or merge the items
- not say that `browse_templates` has "returned", "generated", or "already displayed" the layout

Only one exception:
- if the user explicitly asks for another format, the agent may transform it

## Channel Design

This skill now follows a channel-extension design:
- Business scripts return normalized product / task data
- Python channel renderers transform that data into ready-to-send content
- The agent should treat browse output as final presentation content, not something to reformat

Current implementation:
- `feishu` renderer is implemented and tested

Reserved for future:
- Other communication channels should be added as new renderer / messenger implementations without changing the business scripts
- The agent should not guess unsupported channels or invent channel-specific formatting

## Generator Output Format (MUST FOLLOW)

This skill uses a **two-step generator pattern**.

### Step 1: Browse — Show Templates

After calling `browse_templates`, the tool returns one JSON object with `messagesMarkdown`.

Expected usage:
1. Send each `messagesMarkdown` item **as-is**
2. After the last item, ask the user to choose a `Template ID`

Example:

```json
{
  "format": "multi_message_markdown",
  "messagesMarkdown": [
    "## Canvas Tote Bag\nDurable everyday tote for gifts and custom prints.\n**Template ID:** `12`\n**Price:** **$19.9 USD**\n\n![Canvas Tote](https://...)"
  ]
}
```

**Rules for Step 1:**
- MUST send each returned browse message in order
- MUST preserve the large-image layout inside each message
- MUST send the returned markdown verbatim instead of rewriting it
- Do NOT merge all products back into one summary table
- Do NOT rewrite the returned layout for the current channel unless the user explicitly asks to change the presentation

### Step 2: Generation Complete — Show Preview + Purchase Link

After `get_generation_status` returns COMPLETED, the JSON contains:
- `localImagePath` — preview image in workspace
- `purchaseUrl` — signed purchase/order page link
- `replyMarkdown` — final text message content for the agent to send

You MUST:
1. **Send the preview image as a media attachment** using `localImagePath`
2. **Send `replyMarkdown` exactly as returned** in the text message

Example:

```
[send image: /Users/.../.openclaw/workspace/previews/leewow_preview_task_xxx.jpg]

你的定制效果图出来啦 🎉
🛒 点击下单购买: https://leewow.com/claw/preview/gen_xxx?skid=...&sig=...

喜欢吗？如果想调整或者试试其他产品，告诉我！
```

**Rules for Step 2:**
- MUST send the preview image as media — this is the whole point
- MUST send the returned `replyMarkdown` without paraphrasing
- Do NOT just describe the product in text — the user needs to SEE the image

### Common Mistakes to AVOID

❌ Collapsing the returned per-product messages into one summary table
❌ Claiming that the skill doc does not require the defined browse layout
❌ Applying the generated-preview media rule to `browse_templates`
❌ Adding commentary like "以下是可选模板" before the returned browse messages
❌ Adding follow-up guidance between returned browse messages unless the user asked for it
❌ Saying "browse_templates 已成功返回..." instead of sending the messages themselves
❌ Saying "表格已在上面显示" when the defined browse layout was not actually sent in the current reply
❌ Using `![image](local_path)` markdown for generated preview images — local paths still need media sending
❌ Just saying "完成啦！" and describing the product in text without sending the generated preview image
❌ Omitting the purchase/order link
❌ Dropping the `Template ID` column from the browse table
❌ Saying "图片已下载到本地" without actually sending the generated preview image

## Prerequisites

- `CLAW_SK` — Leewow Secret Key (format: `sk-leewow-{keyId}-{secret}`)
- `CLAW_BASE_URL` — API base URL (default: `https://leewow.com`)
- `CLAW_PATH_PREFIX` — Path prefix (default: `/v2` for leewow.com)
- `LEEWOW_API_BASE` — Base URL for COS STS credentials (default: `https://leewow.com`)
- Python 3.10+ with `requests` and `cos-python-sdk-v5`

## Configuration

Environment variables are loaded from `~/.openclaw/.env`:

```bash
CLAW_SK=sk-leewow-xxxx-xxxx
CLAW_BASE_URL=https://leewow.com
CLAW_PATH_PREFIX=/v2
LEEWOW_API_BASE=https://leewow.com
```

## Image Requirements (IMPORTANT)

### For Input Images (User Upload)
- **Must be in workspace directory**: `~/.openclaw/workspace/`
- Supported formats: JPG, PNG, WebP
- Recommended: Clear, well-lit images for best results

### For Preview Images (Generated Output)
- Automatically saved to: `~/.openclaw/workspace/previews/`
- Filename format: `leewow_preview_{taskId}.{ext}`
- The agent can directly display these images to users

### COS Presigned URLs
For private COS buckets, you may need to generate **presigned URLs** for accessing images:

```bash
# Generate presigned URL for a COS image
python3 scripts/cos_presign.py "https://bucket.cos.region.myqcloud.com/key.png" --json

# With custom expiration (e.g., 1 hour = 3600 seconds)
python3 scripts/cos_presign.py "COS_URL" --expired 3600

# Use with get_generation_status to get presigned preview URL
python3 scripts/get_status.py {taskId} --presign --json
```

**Note**: Most Leewow COS buckets are public, so presigned URLs are optional.

## Typical Flow (Generator Pattern)

1. **Browse (Step 1)** — Call `browse_templates` → get `messagesMarkdown` → send each message directly in order → ask user to pick
2. **Upload** — User provides an image (must be in workspace `~/.openclaw/workspace/`)
3. **Generate** — Call `generate_preview` → get taskId → immediately proceed to step 4
4. **Poll** — Call `get_generation_status` with `poll=true` → wait for COMPLETED
5. **Display (Step 2)** — **Send preview image as media** (`localImagePath`) + then send `replyMarkdown` exactly as returned

## Tool Reference

### browse_templates

Browse available product templates.

```bash
python3 scripts/browse.py --count 5 --json
```

Options:
- `--category`: Filter by category (bag, accessory, home, apparel)
- `--count`: Number of products to return (1-10, default 5)
- `--json`: Output delivery JSON with `messagesMarkdown`
- `--raw-json`: Debug mode that returns raw template data

### generate_preview

Upload image and trigger generation.

```bash
python3 scripts/generate.py --image-path ./workspace/my_design.png --template-id 3 --json
```

Options:
- `--image-path`: **Required**. Path to design image (must be in workspace)
- `--template-id`: **Required**. Product template ID from browse_templates
- `--design-theme`: Optional style description
- `--aspect-ratio`: Image ratio (3:4, 1:1, 4:3, default 3:4)
- `--json`: Output JSON format

**Returns**: Task ID for status polling. Generation is async (~30-60s).

### get_generation_status

Check generation status and download preview image.

```bash
python3 scripts/get_status.py {taskId} --poll
```

Options:
- `task_id`: Task ID from generate_preview
- `--poll`: Wait until generation completes
- `--timeout`: Poll timeout in seconds (default 120)
- `--no-download`: Skip downloading preview image
- `--json`: Output JSON format

**Returns**: Generation status and local image path (if completed).
The agent should use `replyMarkdown` as the final text reply content.

## Safety Rules

- Never expose or log the `CLAW_SK` value. When confirming configuration, only show the last 4 characters.
- Input images **must** be in workspace directory for the agent to access them
- Preview images are automatically saved to `workspace/previews/`
- Limit browse results to 10 templates maximum per request

## Examples

```text
User: "I want to make a custom gift for my friend"
→ browse_templates → send each returned browse message directly
→ user picks → generate_preview → get_generation_status --poll
→ send preview image as media + send `replyMarkdown` directly

User: "Turn this photo into a phone case"
→ browse_templates --category phone → send each returned browse message directly → user picks
→ generate_preview → get_generation_status --poll
→ send preview image as media + send `replyMarkdown` directly

User: "Show me what products I can customize"
→ browse_templates → send each returned browse message
```

## Output Structure

### browse_templates
```json
{
  "format": "multi_message_markdown",
  "messageCount": 1,
  "messagesMarkdown": [
    "## Men's Hoodie\nClassic hoodie with soft fleece lining.\n**Template ID:** `3`\n**Price:** **$29.9 USD**\n\n![Men's Hoodie](https://...)"
  ]
}
```
→ Agent sends each `messagesMarkdown` item directly as one message.

### generate_preview --json
```json
{
  "taskId": "task_xxx",
  "status": "PENDING",
  "estimatedSeconds": 45,
  "templateId": 3
}
```

### get_generation_status --json (completed)
```json
{
  "taskId": "task_xxx",
  "status": "COMPLETED",
  "purchaseUrl": "https://leewow.com/claw/preview/gen_xxx?skid=...&sig=...",
  "localImagePath": "/Users/.../.openclaw/workspace/previews/leewow_preview_task_xxx.jpg",
  "replyMarkdown": "你的定制效果图出来啦 🎉\\n\\n🛒 点击下单购买: https://..."
}
```
→ Agent sends `localImagePath` as media attachment + `replyMarkdown` as text.

Version Marker: custom-gift-leewow@1.0.12
