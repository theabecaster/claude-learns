import { execSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const CORRECTION_PATTERN =
  /\bdon'?t\b|\bnever\b|\balways\b|\bstop\s|\bfrom now on\b|\bI prefer\b|\buse .+ instead\b|\binstead of\b|\bno,\s|\bremember to\b|\bplease don'?t\b|\bI want you to\b/i;

function getProjectDir(): string {
  return process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
}

function loadConfig(): { maxRules: number } {
  const configPath = join(getProjectDir(), ".claude-learns.json");
  const defaults = { maxRules: 50 };
  if (existsSync(configPath)) {
    try {
      const loaded = JSON.parse(readFileSync(configPath, "utf8"));
      return { ...defaults, ...loaded };
    } catch {
      // ignore
    }
  }
  return defaults;
}

function extractRuleViaCLI(prompt: string): string | null {
  try {
    const system =
      "Extract a single clean terse coding preference rule. Output ONLY the rule, max 15 words, start with action verb.";
    const result = execSync(
      `claude -p ${JSON.stringify(prompt)} --system-prompt ${JSON.stringify(system)} --model claude-haiku-4-5`,
      { timeout: 15000, encoding: "utf8" }
    );
    const rule = result.trim().replace(/^["']|["']$/g, "");
    return rule || null;
  } catch {
    return null;
  }
}

function getExistingRules(content: string): string[] {
  const rules: string[] = [];
  let inSection = false;
  for (const line of content.split("\n")) {
    if (line.trim() === "## Learned Preferences") {
      inSection = true;
      continue;
    }
    if (inSection) {
      if (line.startsWith("## ") && line.trim() !== "## Learned Preferences") break;
      const m = line.match(/^- \[\d{4}-\d{2}-\d{2}\] (.+)$/);
      if (m) rules.push(m[1].trim());
    }
  }
  return rules;
}

function isSimilarRule(newRule: string, existing: string[]): boolean {
  const newLower = newRule.toLowerCase();
  return existing.some((e) => {
    const ex = e.toLowerCase();
    return newLower.includes(ex) || ex.includes(newLower);
  });
}

function appendRuleToContent(content: string, rule: string, today: string): string {
  const header = "## Learned Preferences";
  const entry = `- [${today}] ${rule}`;

  if (content.includes(header)) {
    const lines = content.split("\n");
    const result: string[] = [];
    let inSection = false;
    let inserted = false;
    for (const line of lines) {
      result.push(line);
      if (line.trim() === header) {
        inSection = true;
        continue;
      }
      if (inSection && !inserted) {
        if (line.startsWith("## ") && line.trim() !== header) {
          result.splice(result.length - 1, 0, entry);
          inserted = true;
          inSection = false;
        }
      }
    }
    if (inSection && !inserted) {
      if (result[result.length - 1] !== "") result.push("");
      result.push(entry);
    }
    return result.join("\n");
  } else {
    if (content && !content.endsWith("\n")) content += "\n";
    return `${content}\n${header}\n\n${entry}\n`;
  }
}

try {
  let raw = "";
  try {
    raw = readFileSync("/dev/stdin", "utf8");
  } catch {
    process.exit(0);
  }

  let prompt = "";
  try {
    const data = JSON.parse(raw);
    prompt = data?.prompt ?? "";
  } catch {
    process.exit(0);
  }

  if (!prompt || !CORRECTION_PATTERN.test(prompt)) process.exit(0);

  let rule = extractRuleViaCLI(prompt) ?? prompt.slice(0, 100);
  if (!rule) process.exit(0);

  const config = loadConfig();
  const claudeMdPath = join(getProjectDir(), "CLAUDE.md");
  let content = "";
  if (existsSync(claudeMdPath)) {
    try { content = readFileSync(claudeMdPath, "utf8"); } catch { /* ignore */ }
  }

  const existing = getExistingRules(content);
  if (isSimilarRule(rule, existing)) process.exit(0);
  if (existing.length >= config.maxRules) process.exit(0);

  const today = new Date().toISOString().slice(0, 10);
  const newContent = appendRuleToContent(content, rule, today);
  writeFileSync(claudeMdPath, newContent, "utf8");

  console.log(`✅ claude-learns: Captured → ${rule}`);
  process.exit(0);
} catch {
  process.exit(0);
}
