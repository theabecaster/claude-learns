# /claude-learns:clear

Ask the user to confirm before making any changes:

> "This will remove the entire **## Learned Preferences** section from CLAUDE.md. Are you sure? (yes/no)"

If the user confirms:
1. Read CLAUDE.md
2. Count the number of rules in the `## Learned Preferences` section
3. Remove the entire section (the `## Learned Preferences` heading and all lines until the next `##` heading or end of file)
4. Write the updated CLAUDE.md
5. Report: "🗑️ Cleared N learned preferences from CLAUDE.md."

If the user declines, say: "Cancelled — no changes made."

If CLAUDE.md or the section doesn't exist, say: "Nothing to clear — no learned preferences found."
