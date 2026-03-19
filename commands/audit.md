# /claude-learns:audit

Run the audit script to prune expired rules, remove duplicates, and resolve conflicts.

Execute: `tsx ${CLAUDE_PLUGIN_ROOT}/hooks/audit.ts`

Report what was pruned using the script's output. If the script reports nothing changed, say: "✅ No changes needed — all rules are current."
