---
name: custom-gift-leewow
description: >-
  Browse and create custom gifts — personalized bags, mugs, phone cases,
  apparel and more. Upload any image to generate an AI-powered product mockup.
  Includes tools: browse_templates (discover products), generate_preview
  (create a design from an image), and get_status (check generation progress).
  Automatically downloads preview images to workspace for display.
  Powered by Leewow. Requires CLAW_SK.
---

# Custom Gift — Leewow

Create personalized gifts and custom products powered by AI. This skill provides:

| Tool | Purpose |
|------|---------|
| `browse_templates` | Discover customizable product templates (bags, accessories, home decor, apparel, etc.) |
| `generate_preview` | Upload a design image and trigger AI generation |
| `get_status` | Check generation status and download preview image |

## When to Use

- User wants to **send a gift** or **create something personalized**
- User says "browse products", "show me what I can customize", "gift ideas"
- User provides an **image** and wants to turn it into a product
- User says "make this into a mug/bag/shirt", "customize this design"

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

## Typical Flow

1. **Browse** — Use `browse_templates` to show available products
2. **Upload** — User provides an image (must be in workspace)
3. **Generate** — Use `generate_preview` to start AI generation (returns taskId)
4. **Poll** — Use `get_status --poll` to wait for completion
5. **Display** — Preview image is automatically downloaded and can be shown to user

## Tool Reference

### browse_templates

Browse available product templates.

```bash
python3 scripts/browse.py --count 3 --json
```

Options:
- `--category`: Filter by category (bag, accessory, home, apparel)
- `--count`: Number of results (1-5, default 3)
- `--json`: Output JSON format (includes image URLs)

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

### get_status

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

## Safety Rules

- Never expose or log the `CLAW_SK` value. When confirming configuration, only show the last 4 characters.
- Input images **must** be in workspace directory for the agent to access them
- Preview images are automatically saved to `workspace/previews/`
- Limit browse results to 5 templates maximum per request

## Examples

```text
User: "I want to make a custom gift for my friend"
→ Use browse_templates → user picks template → get image path from user → 
  generate_preview → poll with get_status → display preview image

User: "Turn this photo into a phone case"
→ browse_templates --category phone → user picks → generate_preview → 
  get_status --poll → show downloaded preview image

User: "Show me what products I can customize"
→ browse_templates --json → display product cards with images
```

## Output Structure

### browse_templates --json
```json
[
  {
    "templateId": 3,
    "name": "Hoodie",
    "coverImage": "https://...",
    "description": "...",
    "skuType": "hoodie"
  }
]
```

### generate_preview --json
```json
{
  "taskId": "task_xxx",
  "status": "PENDING",
  "estimatedSeconds": 45,
  "templateId": 3,
  "_success": true
}
```

### get_status --json (completed)
```json
{
  "taskId": "task_xxx",
  "status": "COMPLETED",
  "previewUrl": "https://...",
  "previewImageUrl": "https://...",
  "localImagePath": "/Users/.../.openclaw/workspace/previews/leewow_preview_task_xxx.jpg"
}
```
