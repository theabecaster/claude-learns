# claude-learns

> Claude Code that learns from you

Every time you correct Claude Code mid-session, `claude-learns` captures the correction, extracts a clean rule, and saves it to your project's `CLAUDE.md`. At session end, it automatically audits: expiring stale rules, deduplicating, and resolving conflicts — so your preferences stay sharp and CLAUDE.md stays slim.

---

## Install

Clone the repo, then load it with the `--plugin-dir` flag when starting Claude Code:

```bash
git clone https://github.com/theabecaster/claude-learns
cd your-project
claude --plugin-dir ~/path/to/claude-learns
```

Or if you cloned it to your home directory:

```bash
claude --plugin-dir ~/claude-learns
```

> **Tip:** Add an alias to your shell profile so every Claude Code session loads the plugin automatically:
> ```bash
> alias claude='claude --plugin-dir ~/claude-learns'
> ```

---

## Requirements

- Claude Code 1.0.33+
- Node.js 18+ (already installed with Claude Code)
- `tsx` (TypeScript runner):
  ```bash
  npm install -g tsx
  ```

---

## How It Works

- **Auto-capture** — Every prompt is scanned for correction signals (`"don't"`, `"always"`, `"I prefer"`, `"from now on"`, etc.). When matched, an Anthropic API call extracts a clean ≤15-word rule and appends it to `CLAUDE.md`.
- **Persistent memory** — Rules live in a `## Learned Preferences` section in your `CLAUDE.md`, so Claude reads them at every session start automatically.
- **Self-auditing** — At session end, expired rules are pruned, duplicates removed, and conflicts resolved. Your CLAUDE.md stays lean.

---

## Demo

After starting Claude Code with the plugin loaded, type any correction:

```
don't use var, always use const
```

You'll see:

```
✅ claude-learns: Captured → Use const instead of var in JavaScript
```

And your `CLAUDE.md` will contain:

```markdown
## Learned Preferences
<!-- Last audited: 2026-03-18 | Rules: 1 | TTL: 30d -->

- [2026-03-18] Use const instead of var in JavaScript
```

Next session, Claude already knows.

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
| `conflictResolution` | `"keep-newer"` | Strategy when conflicting rules are found |

---

## Commands

Once the plugin is loaded, these slash commands are available inside Claude Code:

| Command | Description |
|---|---|
| `/claude-learns:review` | List all active learned preferences with dates and total count |
| `/claude-learns:audit` | Manually trigger the audit (prune expired, dedup, resolve conflicts) |
| `/claude-learns:clear` | Remove all learned preferences from CLAUDE.md (asks for confirmation) |

---

## How It Works Under the Hood

Three hooks run automatically throughout your session:

1. **`UserPromptSubmit`** — `detect-correction.ts` scans every prompt with a regex for correction signals. On a match, it calls `claude-haiku-4-5` to extract a clean rule (falls back to trimmed raw prompt if the API is unavailable), deduplicates against existing rules, and appends to `CLAUDE.md`.

2. **`SessionStart`** — `session-count.ts` counts active rules and prints a brief summary so you know your preferences are loaded.

3. **`SessionEnd`** — `audit.ts` runs async. It expires rules older than `ttlDays`, removes near-exact duplicates, calls the API once to find and resolve semantic conflicts, trims to `maxRules`, and updates the `Last audited` comment in `CLAUDE.md`.

All scripts exit 0 and handle errors gracefully — API failures, missing files, and bad input never crash your session.

---

## License

MIT © [theabecaster](https://github.com/theabecaster)
