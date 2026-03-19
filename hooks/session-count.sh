#!/usr/bin/env bash
# session-count.sh — SessionStart hook for claude-learns.
# Counts active learned preferences and prints a summary.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
CLAUDE_MD="$PROJECT_DIR/CLAUDE.md"

if [ ! -f "$CLAUDE_MD" ]; then
    exit 0
fi

# Check if the section exists
if ! grep -q "^## Learned Preferences" "$CLAUDE_MD" 2>/dev/null; then
    exit 0
fi

# Count rule lines in the section (lines matching ^- [ between ## Learned Preferences and next ## heading)
count=$(awk '
    /^## Learned Preferences/ { in_section=1; next }
    in_section && /^## / { in_section=0 }
    in_section && /^\- \[/ { count++ }
    END { print count+0 }
' "$CLAUDE_MD")

if [ "$count" -gt 0 ]; then
    echo "📚 claude-learns: $count learned preferences active"
fi

exit 0
