# claude-learns

> Claude Code that learns from you

Every time you correct Claude Code mid-session, `claude-learns` captures the correction, extracts a clean rule, and saves it to your project's `CLAUDE.md`. At session end, it automatically audits: expiring stale rules, deduplicating, and resolving conflicts.

---

## Install

```bash
/plugin install github:theabecaster/claude-learns
```

---

## How It Works

- **Auto-capture** — Every prompt is scanned for correction signals ("don't", "always", "I prefer", etc.). Matches are sent to the Anthropic API to extract a clean, terse rule (≤15 words), then appended to `CLAUDE.md`.
- **Persistent memory** — Rules live in a `## Learned Preferences` section in your project's `CLAUDE.md`, so Claude reads them on every session start.
- **Self-auditing** — On session end, expired rules are pruned, duplicates removed, and conflicts resolved automatically.

---

## Demo

![claude-learns demo](https://placeholder.example.com/demo.gif)

*GIF coming soon — contributions welcome!*

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
| `ttlDays` | `30` | Days before a rule expires |
| `maxRules` | `50` | Maximum rules to keep (trims oldest) |
| `conflictResolution` | `"keep-newer"` | Strategy for resolving conflicts |

---

## Commands

| Command | Description |
|---|---|
| `/claude-learns:review` | List all active learned preferences with dates and count |
| `/claude-learns:audit` | Manually trigger the audit (prune, dedup, resolve conflicts) |
| `/claude-learns:clear` | Remove all learned preferences from CLAUDE.md (with confirmation) |

---

## How It Works Under the Hood

1. **`UserPromptSubmit` hook** — `detect-correction.py` reads every prompt from stdin. If a correction signal regex matches, it calls the Anthropic API (`claude-haiku-4-5`) to extract a clean rule (falls back to trimmed raw prompt if the API is unavailable). The rule is appended to `CLAUDE.md` under `## Learned Preferences` with a datestamp.

2. **`SessionStart` hook** — `session-count.sh` counts active rules and prints a summary so you know your preferences are loaded.

3. **`SessionEnd` hook** — `audit.py` runs asynchronously. It expires rules older than `ttlDays`, removes near-exact duplicates, calls the API once to identify and resolve semantic conflicts, trims to `maxRules`, and updates the audit metadata comment in `CLAUDE.md`.

All scripts exit 0 and never crash — file I/O errors and API failures are handled gracefully.

---

## Requirements

- Python 3.10+
- `anthropic` Python package (for AI-powered rule extraction):
  ```bash
  pip install anthropic
  ```
- `ANTHROPIC_API_KEY` environment variable set

If `anthropic` is not installed, the plugin falls back to regex-only rule capture (no conflict resolution). Install hints are printed to stderr.

---

## License

MIT © theabecaster
