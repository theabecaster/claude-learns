# claude-learns

> Claude Code that learns from you

Every time you correct Claude Code mid-session, `claude-learns` captures the correction, extracts a clean rule, and saves it to your project's `CLAUDE.md`. Next session, Claude already knows. Rules are automatically audited — expiring stale ones, removing duplicates, resolving conflicts — so your preferences stay sharp and `CLAUDE.md` stays slim.

---

## Install

**Step 1** — Add the marketplace (one time):
```
/plugin marketplace add theabecaster/claude-plugins
```

**Step 2** — Install the plugin:
```
/plugin install claude-learns@abe-plugins
```

**Step 3** — Install `tsx` (TypeScript runner, required):
```bash
npm install -g tsx
```

That's it. Restart Claude Code and the plugin is active.

---

## Requirements

- Claude Code 1.0.33+
- Node.js 18+ (already included with Claude Code)
- `tsx`: `npm install -g tsx`

---

## How It Works

- **Auto-capture** — Every prompt is scanned for correction signals (`"don't"`, `"never"`, `"always"`, `"I prefer"`, `"from now on"`, etc.). When matched, the `claude` CLI extracts a clean ≤15-word rule and appends it to `CLAUDE.md`.
- **Persistent memory** — Rules live in a `## Learned Preferences` section in your project's `CLAUDE.md`, which Claude Code reads automatically at every session start.
- **Self-auditing** — At session end, expired rules are pruned, duplicates removed, and conflicts resolved. Your `CLAUDE.md` stays lean.

---

## Demo

Type any correction in Claude Code:

```
never use var, always use const or let
```

You'll see:

```
✅ claude-learns: Captured → Use const or let instead of var
```

Your `CLAUDE.md` gets updated automatically:

```markdown
## Learned Preferences
<!-- Last audited: 2026-03-18 | Rules: 1 | TTL: 30d -->

- [2026-03-18] Use const or let instead of var
```

Next session, Claude already knows. No repeating yourself.

---

## Configuration

Create a `.claude-learns.json` in your project root to customize behavior:

```json
{
  "ttlDays": 30,
  "maxRules": 50,
  "conflictResolution": "keep-newer"
}
```

| Key | Default | Description |
|---|---|---|
| `ttlDays` | `30` | Days before a rule expires and is pruned |
| `maxRules` | `50` | Maximum rules to keep (trims oldest when exceeded) |
| `conflictResolution` | `"keep-newer"` | Strategy when conflicting rules are detected |

---

## Commands

| Command | Description |
|---|---|
| `/claude-learns:review` | List all active learned preferences with dates and total count |
| `/claude-learns:audit` | Manually trigger audit (prune expired, dedup, resolve conflicts) |
| `/claude-learns:clear` | Remove all learned preferences from CLAUDE.md (with confirmation) |

---

## How It Works Under the Hood

Three hooks run automatically:

1. **`UserPromptSubmit`** — `detect-correction.ts` scans every prompt for correction signals. On a match, it calls the `claude` CLI to extract a clean rule, deduplicates against existing rules, and appends to `CLAUDE.md`.

2. **`SessionStart`** — `session-count.ts` counts active rules and prints a brief summary so you know your preferences are loaded.

3. **`SessionEnd`** — `audit.ts` runs async. Expires rules older than `ttlDays`, removes near-exact duplicates, resolves semantic conflicts via the `claude` CLI, trims to `maxRules`, and updates the `Last audited` comment.

All scripts exit 0 and handle errors gracefully — failures never interrupt your session.

---

## License

MIT © [theabecaster](https://github.com/theabecaster)
