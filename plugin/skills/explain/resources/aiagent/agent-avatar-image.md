---
topic: agent-avatar-image
description: Custom avatar image on AI Agent — data URI pattern, imageOptimizedFormat, file spec, push_agent_avatar usage
---

## agent-avatar-image — Setting a Custom AI Agent Avatar

### The image field

The `image` field on an AI Agent resource accepts two value shapes:

| Value | Meaning |
|---|---|
| `"default-avatar:N"` | Platform preset — N is 0-based (0, 1, 2, …) |
| `"data:image/png;base64,<b64>"` | Custom image as a data URI |

Always include `imageOptimizedFormat` in the update body alongside `image` — the platform sets this field regardless of which image type is used.

### File spec for a standout avatar

| Property | Value |
|---|---|
| Width | 136 px |
| Height | 184 px |
| Background | Transparent |
| Format | PNG |
| Filename convention | Include `_optimized` in the filename (e.g. `quinn_optimized.png`) |

The portrait aspect ratio (136 × 184) fills the Cognigy avatar slot without cropping. A transparent background blends cleanly across UI themes.

### Pushing a custom avatar

Use `push_agent_avatar` — it validates dimensions, encodes, and PATCHes in one step:

```
push_agent_avatar(
    image_file="/absolute/path/to/quinn_optimized.png",
    agent_id="<agent _id or referenceId>",
)
```

The tool rejects images that are not exactly 136×184px. If the aspect ratio is correct but the size is wrong, it reports the exact target to resize to.

### Reverting to a platform preset

Use `cognigy_update` directly — no file encoding needed:

```
cognigy_update(
    resource_type="aiagents",
    resource_id="<agent _id or referenceId>",
    body={
        "image": "default-avatar:0",
        "imageOptimizedFormat": True,
    }
)
```

### Discovery reference

Quinn agent (Qantas Demo project) — custom avatar:
```json
{ "image": "data:image/png;base64,iVBORw0KGgo…", "imageOptimizedFormat": true }
```

Sammy agent — platform preset:
```json
{ "image": "default-avatar:0", "imageOptimizedFormat": true }
```
