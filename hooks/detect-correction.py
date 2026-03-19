#!/usr/bin/env python3
"""
detect-correction.py — UserPromptSubmit hook for claude-learns.
Reads a prompt from stdin, checks for correction signals, extracts a rule,
and appends it to CLAUDE.md under "## Learned Preferences".
"""

import json
import os
import re
import sys
from datetime import date

# ---------------------------------------------------------------------------
# Try to import anthropic; fall back gracefully if not installed
# ---------------------------------------------------------------------------
try:
    import anthropic as _anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print(
        "💡 claude-learns: Run `pip install anthropic` to enable AI-powered rule extraction.",
        file=sys.stderr,
    )

# ---------------------------------------------------------------------------
# Correction signal patterns
# ---------------------------------------------------------------------------
CORRECTION_PATTERNS = re.compile(
    r"\bdon'?t\b|"
    r"\bnever\b|"
    r"\balways\b|"
    r"\bstop\s|"
    r"\bfrom now on\b|"
    r"\bI prefer\b|"
    r"\buse .+ instead\b|"
    r"\binstead of\b|"
    r"\bno,\s|"
    r"\bremember to\b|"
    r"\bplease don'?t\b|"
    r"\bI want you to\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())


def get_claude_md_path() -> str:
    return os.path.join(get_project_dir(), "CLAUDE.md")


def load_config() -> dict:
    config_path = os.path.join(get_project_dir(), ".claude-learns.json")
    defaults = {"ttlDays": 30, "maxRules": 50}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                defaults.update(loaded)
        except Exception:
            pass
    return defaults


def extract_rule_via_api(prompt: str) -> str | None:
    """Call Anthropic API to extract a clean rule. Returns None on failure."""
    if not ANTHROPIC_AVAILABLE:
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        client = _anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=60,
            system=(
                "You extract a single, clean, terse coding preference rule from user messages. "
                "Output ONLY the rule itself — no explanation, no quotes, no punctuation at the end. "
                "Maximum 15 words. Start with an action verb or noun."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if block.type == "text":
                rule = block.text.strip().strip('"\'')
                if rule:
                    return rule
    except Exception:
        pass
    return None


def is_similar_rule(new_rule: str, existing_rules: list[str]) -> bool:
    """Simple substring deduplication (case-insensitive)."""
    new_lower = new_rule.lower()
    for existing in existing_rules:
        ex_lower = existing.lower()
        if new_lower in ex_lower or ex_lower in new_lower:
            return True
    return False


def read_claude_md() -> str:
    path = get_claude_md_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""
    return ""


def write_claude_md(content: str) -> None:
    path = get_claude_md_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"claude-learns: Failed to write CLAUDE.md: {e}", file=sys.stderr)


def get_existing_rules(content: str) -> list[str]:
    """Extract rule text from '- [YYYY-MM-DD] <rule>' lines in the LP section."""
    rules = []
    in_section = False
    for line in content.splitlines():
        if line.strip() == "## Learned Preferences":
            in_section = True
            continue
        if in_section:
            if line.startswith("## ") and line.strip() != "## Learned Preferences":
                break
            m = re.match(r"^- \[\d{4}-\d{2}-\d{2}\] (.+)$", line)
            if m:
                rules.append(m.group(1).strip())
    return rules


def append_rule_to_content(content: str, rule: str, today: str) -> str:
    """Insert rule into ## Learned Preferences section, creating it if absent."""
    section_header = "## Learned Preferences"
    new_entry = f"- [{today}] {rule}"

    if section_header in content:
        # Find end of the section (next ## heading or EOF)
        lines = content.splitlines(keepends=True)
        result = []
        in_section = False
        inserted = False
        for i, line in enumerate(lines):
            result.append(line)
            if line.strip() == section_header:
                in_section = True
                continue
            if in_section and not inserted:
                # Look ahead: insert before next top-level heading or at EOF
                stripped = line.strip()
                if stripped.startswith("## ") and stripped != section_header:
                    # Insert before this line
                    result.insert(-1, new_entry + "\n")
                    inserted = True
                    in_section = False
        if in_section and not inserted:
            # Append at end of file
            if result and not result[-1].endswith("\n"):
                result.append("\n")
            result.append(new_entry + "\n")
        return "".join(result)
    else:
        # Append section to end of file
        if content and not content.endswith("\n"):
            content += "\n"
        content += f"\n{section_header}\n\n{new_entry}\n"
        return content


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Read stdin
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
        prompt = data.get("prompt", "")
    except Exception:
        sys.exit(0)

    if not prompt:
        sys.exit(0)

    # Fast path: no correction signal
    if not CORRECTION_PATTERNS.search(prompt):
        sys.exit(0)

    # Extract rule
    rule = extract_rule_via_api(prompt)
    if not rule:
        # Fallback: trim raw prompt
        rule = prompt.strip()[:100]

    if not rule:
        sys.exit(0)

    # Load config and existing content
    config = load_config()
    content = read_claude_md()
    existing_rules = get_existing_rules(content)

    # Dedup check
    if is_similar_rule(rule, existing_rules):
        sys.exit(0)

    # Enforce maxRules before appending
    # (trimming is handled in audit; here we just skip if already at limit)
    if len(existing_rules) >= config.get("maxRules", 50):
        sys.exit(0)

    # Append rule
    today = date.today().strftime("%Y-%m-%d")
    new_content = append_rule_to_content(content, rule, today)
    write_claude_md(new_content)

    print(f"✅ claude-learns: Captured → {rule}")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
