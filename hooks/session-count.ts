import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

try {
  const projectDir = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
  const claudeMdPath = join(projectDir, "CLAUDE.md");

  if (!existsSync(claudeMdPath)) process.exit(0);

  const content = readFileSync(claudeMdPath, "utf8");
  let count = 0;
  let inSection = false;

  for (const line of content.split("\n")) {
    if (line.trim() === "## Learned Preferences") { inSection = true; continue; }
    if (inSection) {
      if (line.startsWith("## ") && line.trim() !== "## Learned Preferences") break;
      if (/^- \[\d{4}-\d{2}-\d{2}\]/.test(line)) count++;
    }
  }

  if (count > 0) console.log(`📚 claude-learns: ${count} learned preferences active`);
  process.exit(0);
} catch {
  process.exit(0);
}
