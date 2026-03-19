import { execSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

function getProjectDir(): string {
  return process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
}

function loadConfig(): { ttlDays: number; maxRules: number; conflictResolution: string } {
  const configPath = join(getProjectDir(), ".claude-learns.json");
  const defaults = { ttlDays: 30, maxRules: 50, conflictResolution: "keep-newer" };
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

interface Rule {
  date: string;
  text: string;
}

function parseSection(content: string): { before: string; sectionLines: string[]; after: string } {
  const lines = content.split("\n");
  let headerIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() === "## Learned Preferences") {
      headerIdx = i;
      break;
    }
  }
  if (headerIdx === -1) return { before: content, sectionLines: [], after: "" };

  let sectionEnd = lines.length;
  for (let i = headerIdx + 1; i < lines.length; i++) {
    if (lines[i].trim().startsWith("## ") && lines[i].trim() !== "## Learned Preferences") {
      sectionEnd = i;
      break;
    }
  }

  return {
    before: lines.slice(0, headerIdx + 1).join("\n"),
    sectionLines: lines.slice(headerIdx + 1, sectionEnd),
    after: lines.slice(sectionEnd).join("\n"),
  };
}

function parseRuleLines(lines: string[]): Rule[] {
  const rules: Rule[] = [];
  for (const line of lines) {
    const m = line.match(/^- \[(\d{4}-\d{2}-\d{2})\] (.+)$/);
    if (m) rules.push({ date: m[1], text: m[2].trim() });
  }
  return rules;
}

function expireRules(rules: Rule[], ttlDays: number): { kept: Rule[]; expiredCount: number } {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  let expiredCount = 0;
  const kept = rules.filter((r) => {
    try {
      const d = new Date(r.date);
      const diffDays = Math.floor((today.getTime() - d.getTime()) / 86400000);
      if (diffDays <= ttlDays) return true;
      expiredCount++;
      return false;
    } catch {
      return true;
    }
  });
  return { kept, expiredCount };
}

function normalize(text: string): string {
  return text.toLowerCase().replace(/\s+/g, " ").trim();
}

function dedupRules(rules: Rule[]): { kept: Rule[]; dedupCount: number } {
  const seen: string[] = [];
  let dedupCount = 0;
  const kept = rules.filter((r) => {
    const n = normalize(r.text);
    const isDup = seen.some((s) => n.includes(s) || s.includes(n));
    if (isDup) { dedupCount++; return false; }
    seen.push(n);
    return true;
  });
  return { kept, dedupCount };
}

function resolveConflictsViaCLI(rules: Rule[]): { kept: Rule[]; conflictCount: number } {
  if (rules.length < 2) return { kept: rules, conflictCount: 0 };
  try {
    execSync("which claude", { stdio: "ignore" });
  } catch {
    return { kept: rules, conflictCount: 0 };
  }

  const rulesText = rules.map((r, i) => `${i}: ${r.text}`).join("\n");
  const prompt =
    `Here are coding preference rules (index: rule):\n\n${rulesText}\n\n` +
    "Identify pairs of rules that directly contradict each other. " +
    "For each conflicting pair, specify which index to REMOVE (keep the higher-indexed/newer one). " +
    'Return a JSON object with key \'remove\' containing a list of integer indices to remove. ' +
    'If no conflicts, return {"remove": []}. Return ONLY the JSON object.';

  try {
    const result = execSync(
      `claude -p ${JSON.stringify(prompt)} --model claude-haiku-4-5`,
      { timeout: 20000, encoding: "utf8" }
    );
    const jsonMatch = result.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const data = JSON.parse(jsonMatch[0]);
      const toRemove = new Set<number>(data.remove ?? []);
      if (toRemove.size > 0) {
        const kept = rules.filter((_, i) => !toRemove.has(i));
        return { kept, conflictCount: toRemove.size };
      }
    }
  } catch {
    // ignore
  }
  return { kept: rules, conflictCount: 0 };
}

function rebuildContent(
  before: string,
  sectionLines: string[],
  after: string,
  rules: Rule[],
  ttlDays: number
): string {
  const today = new Date().toISOString().slice(0, 10);
  const auditComment = `<!-- Last audited: ${today} | Rules: ${rules.length} | TTL: ${ttlDays}d -->`;

  const nonRuleLines = sectionLines.filter(
    (l) => !l.match(/^- \[\d{4}-\d{2}-\d{2}\]/) && !l.trim().startsWith("<!-- Last audited:")
  );
  const ruleLines = rules.map((r) => `- [${r.date}] ${r.text}`);
  const newSection = [auditComment, ...nonRuleLines, ...ruleLines].join("\n");

  const afterStr = after.startsWith("\n") ? after : (after ? "\n" + after : "");
  return `${before}\n${newSection}${afterStr}`;
}

try {
  const claudeMdPath = join(getProjectDir(), "CLAUDE.md");
  if (!existsSync(claudeMdPath)) process.exit(0);

  let content = "";
  try { content = readFileSync(claudeMdPath, "utf8"); } catch { process.exit(0); }
  if (!content) process.exit(0);

  const { before, sectionLines, after } = parseSection(content);
  if (sectionLines.length === 0 && !before.trim().endsWith("## Learned Preferences")) process.exit(0);

  const config = loadConfig();
  let rules = parseRuleLines(sectionLines);
  if (rules.length === 0) process.exit(0);

  const { kept: afterExpire, expiredCount } = expireRules(rules, config.ttlDays);
  rules = afterExpire;

  const { kept: afterDedup, dedupCount } = dedupRules(rules);
  rules = afterDedup;

  const { kept: afterConflict, conflictCount } = resolveConflictsViaCLI(rules);
  rules = afterConflict;

  if (rules.length > config.maxRules) rules = rules.slice(-config.maxRules);

  const newContent = rebuildContent(before, sectionLines, after, rules, config.ttlDays);
  writeFileSync(claudeMdPath, newContent, "utf8");

  console.log(
    `🧹 claude-learns: pruned ${expiredCount} expired, ` +
    `resolved ${dedupCount + conflictCount} conflicts, ` +
    `${rules.length} rules active`
  );
  process.exit(0);
} catch {
  process.exit(0);
}
