#!/usr/bin/env python3
"""
audit.py — SessionEnd hook for claude-learns.
Expires old rules, deduplicates, resolves conflicts, trims to maxRules,
and updates the ## Learned Preferences section in CLAUDE.md.
"""

import json
import os
import re
import sys
from datetime import date, datetime

# ---------------------------------------------------------------------------
# Try to import anthropic; fall back gracefully if not installed
# ---------------------------------------------------------------------------
try:
    import anthropic as _anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())


def get_claude_md_path() -> str:
    return os.path.join(get_project_dir(), "CLAUDE.md")


def load_config() -> dict:
    config_path = os.path.join(get_project_dir(), ".claude-learns.json")
    defaults = {"ttlDays": 30, "maxRules": 50, "conflictResolution": "keep-newer"}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                defaults.update(loaded)
        except Exception:
            pass
    return defaults


def read_claude_md() -> str:
    path = get_claude_md_path()
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def write_claude_md(content: str) -> None:
    path = get_claude_md_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"claude-learns audit: Failed to write CLAUDE.md: {e}", file=sys.stderr)


def parse_section(content: str):
    """
    Return (before, section_lines, after) where section_lines are the lines
    between ## Learned Preferences and the next ## heading (or EOF),
    NOT including the header itself.
    Returns (content, [], "") if section not found.
    """
    lines = content.splitlines(keepends=True)
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "## Learned Preferences":
            header_idx = i
            break
    if header_idx is None:
        return content, [], ""

    section_start = header_idx + 1
    section_end = len(lines)
    for i in range(section_start, len(lines)):
        if lines[i].strip().startswith("## ") and lines[i].strip() != "## Learned Preferences":
            section_end = i
            break

    before = "".join(lines[: header_idx + 1])
    section_lines = lines[section_start:section_end]
    after = "".join(lines[section_end:])
    return before, section_lines, after


def rebuild_content(before: str, section_lines: list[str], after: str, rule_count: int, ttl_days: int) -> str:
    today = date.today().strftime("%Y-%m-%d")
    audit_comment = f"<!-- Last audited: {today} | Rules: {rule_count} | TTL: {ttl_days}d -->\n"

    # Remove any existing audit comment from section lines
    filtered = [l for l in section_lines if not l.strip().startswith("<!-- Last audited:")]

    new_section = audit_comment + "".join(filtered)
    return before + "\n" + new_section + after


def parse_rule_lines(section_lines: list[str]) -> list[dict]:
    """Parse rule lines into structured dicts. Non-rule lines are ignored."""
    rules = []
    for line in section_lines:
        m = re.match(r"^- \[(\d{4}-\d{2}-\d{2})\] (.+)$", line.rstrip())
        if m:
            date_str, rule_text = m.group(1), m.group(2).strip()
            rules.append({"date": date_str, "text": rule_text, "line": line})
    return rules


def expire_rules(rules: list[dict], ttl_days: int) -> tuple[list[dict], int]:
    today = date.today()
    kept = []
    expired_count = 0
    for r in rules:
        try:
            rule_date = datetime.strptime(r["date"], "%Y-%m-%d").date()
            delta = (today - rule_date).days
            if delta <= ttl_days:
                kept.append(r)
            else:
                expired_count += 1
        except ValueError:
            kept.append(r)  # Keep rules with unparseable dates
    return kept, expired_count


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def dedup_rules(rules: list[dict]) -> tuple[list[dict], int]:
    seen = []
    deduped = []
    removed = 0
    for r in rules:
        n = normalize(r["text"])
        # Check for near-exact duplicates via substring
        is_dup = False
        for s in seen:
            if n in s or s in n:
                is_dup = True
                break
        if not is_dup:
            seen.append(n)
            deduped.append(r)
        else:
            removed += 1
    return deduped, removed


def resolve_conflicts_via_api(rules: list[dict]) -> tuple[list[dict], int]:
    """
    Call Anthropic API to find conflicting rules and keep the newer ones.
    Returns (kept_rules, conflict_pairs_resolved).
    """
    if not ANTHROPIC_AVAILABLE or len(rules) < 2:
        return rules, 0

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return rules, 0

    rules_text = "\n".join(f"{i}: {r['text']}" for i, r in enumerate(rules))
    prompt = (
        f"Here are coding preference rules (index: rule):\n\n{rules_text}\n\n"
        "Identify pairs of rules that directly contradict each other. "
        "For each conflicting pair, specify which index to REMOVE (keep the higher-indexed/newer one). "
        "Return a JSON object with key 'remove' containing a list of integer indices to remove. "
        "If no conflicts, return {\"remove\": []}. Return ONLY the JSON object."
    )

    try:
        client = _anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if block.type == "text":
                text = block.text.strip()
                # Extract JSON from response
                json_match = re.search(r"\{.*\}", text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    to_remove = set(data.get("remove", []))
                    if to_remove:
                        kept = [r for i, r in enumerate(rules) if i not in to_remove]
                        return kept, len(to_remove)
    except Exception:
        pass

    return rules, 0


def rules_to_lines(rules: list[dict]) -> list[str]:
    return [f"- [{r['date']}] {r['text']}\n" for r in rules]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    content = read_claude_md()
    if not content:
        sys.exit(0)

    before, section_lines, after = parse_section(content)
    if not section_lines and not before.strip().endswith("## Learned Preferences"):
        # Section not found
        sys.exit(0)

    config = load_config()
    ttl_days = config.get("ttlDays", 30)
    max_rules = config.get("maxRules", 50)

    rules = parse_rule_lines(section_lines)

    if not rules:
        sys.exit(0)

    # Step 1: Expire old rules
    rules, expired_count = expire_rules(rules, ttl_days)

    # Step 2: Deduplicate
    rules, dedup_count = dedup_rules(rules)

    # Step 3: Resolve conflicts via API
    rules, conflict_count = resolve_conflicts_via_api(rules)

    # Step 4: Trim to maxRules (keep most recent)
    if len(rules) > max_rules:
        rules = rules[-max_rules:]

    # Rebuild section lines (preserve non-rule lines like blank lines, audit comment)
    non_rule_lines = [l for l in section_lines if not re.match(r"^- \[\d{4}-\d{2}-\d{2}\]", l.strip()) and not l.strip().startswith("<!-- Last audited:")]
    new_section_lines = non_rule_lines + rules_to_lines(rules)

    new_content = rebuild_content(before, new_section_lines, after, len(rules), ttl_days)
    write_claude_md(new_content)

    total_removed = expired_count + dedup_count + conflict_count
    print(
        f"🧹 claude-learns: pruned {expired_count} expired, "
        f"resolved {dedup_count + conflict_count} conflicts, "
        f"{len(rules)} rules active"
    )
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
