/**
 * UserPromptSubmit hook: Cognitive Triage System
 *
 * Analyzes every user prompt for:
 * 1. Complexity scoring (DELIBERATE vs REFLEXIVE mode)
 * 2. Domain routing (FloodSafe-specific agent suggestions)
 * 3. Danger signals (destructive operations warning)
 * 4. Reflection feedback (surfaces relevant past lessons)
 *
 * Input: JSON on stdin with { prompt, session_id, ... }
 * Output: Plain text to stdout (UserPromptSubmit special: stdout becomes Claude context)
 */

const fs = require('fs');
const path = require('path');

// --- Complexity Scoring Patterns ---

const HIGH_WEIGHT = 3;
const MEDIUM_WEIGHT = 2;
const STANDARD_WEIGHT = 1;
const REDUCE_WEIGHT = -2;

const complexityPatterns = [
  // HIGH (3) — Dangerous/destructive operations
  { pattern: /delete\s+table/i, weight: HIGH_WEIGHT, label: 'delete table' },
  { pattern: /drop\s+(table|column|index|database)/i, weight: HIGH_WEIGHT, label: 'drop schema object' },
  { pattern: /schema\s+migration/i, weight: HIGH_WEIGHT, label: 'schema migration' },
  { pattern: /remove\s+database/i, weight: HIGH_WEIGHT, label: 'remove database' },
  { pattern: /reset\s+--hard/i, weight: HIGH_WEIGHT, label: 'git reset --hard' },
  { pattern: /force\s+push/i, weight: HIGH_WEIGHT, label: 'force push' },
  { pattern: /truncate/i, weight: HIGH_WEIGHT, label: 'truncate' },

  // MEDIUM (2) — Requires careful analysis
  { pattern: /\brefactor\b/i, weight: MEDIUM_WEIGHT, label: 'refactor' },
  { pattern: /\bauth\b/i, weight: MEDIUM_WEIGHT, label: 'auth' },
  { pattern: /\bmigration\b/i, weight: MEDIUM_WEIGHT, label: 'migration' },
  { pattern: /\bredesign\b/i, weight: MEDIUM_WEIGHT, label: 'redesign' },
  { pattern: /\bsecurity\b/i, weight: MEDIUM_WEIGHT, label: 'security' },
  { pattern: /\bjwt\b/i, weight: MEDIUM_WEIGHT, label: 'JWT' },
  { pattern: /\bowasp\b/i, weight: MEDIUM_WEIGHT, label: 'OWASP' },
  { pattern: /\bvulnerabilit/i, weight: MEDIUM_WEIGHT, label: 'vulnerability' },
  { pattern: /\bPostGIS\b/i, weight: MEDIUM_WEIGHT, label: 'PostGIS' },
  { pattern: /database\s+schema/i, weight: MEDIUM_WEIGHT, label: 'database schema' },
  { pattern: /\barchitecture\b/i, weight: MEDIUM_WEIGHT, label: 'architecture' },
  { pattern: /multi.?city/i, weight: MEDIUM_WEIGHT, label: 'multi-city' },

  // STANDARD (1) — Normal development tasks
  { pattern: /\bperformance\b/i, weight: STANDARD_WEIGHT, label: 'performance' },
  { pattern: /\boptimize\b/i, weight: STANDARD_WEIGHT, label: 'optimize' },
  { pattern: /\bdebug\b/i, weight: STANDARD_WEIGHT, label: 'debug' },
  { pattern: /\binvestigate\b/i, weight: STANDARD_WEIGHT, label: 'investigate' },
  { pattern: /\bimplement\b/i, weight: STANDARD_WEIGHT, label: 'implement' },
  { pattern: /\bcreate\b/i, weight: STANDARD_WEIGHT, label: 'create' },
  { pattern: /\bbuild\b/i, weight: STANDARD_WEIGHT, label: 'build' },
  { pattern: /add\s+feature/i, weight: STANDARD_WEIGHT, label: 'add feature' },

  // REDUCE (-2) — Simple tasks that don't need deep analysis
  { pattern: /fix\s+typo/i, weight: REDUCE_WEIGHT, label: 'fix typo' },
  { pattern: /add\s+import/i, weight: REDUCE_WEIGHT, label: 'add import' },
  { pattern: /rename\s+variable/i, weight: REDUCE_WEIGHT, label: 'rename variable' },
  { pattern: /update\s+comment/i, weight: REDUCE_WEIGHT, label: 'update comment' },
  { pattern: /add\s+log/i, weight: REDUCE_WEIGHT, label: 'add log' },
  { pattern: /fix\s+lint/i, weight: REDUCE_WEIGHT, label: 'fix lint' },
];

// --- Domain Routing ---

const domainRoutes = [
  {
    agent: 'ml-data',
    keywords: /\bFHI\b|\bXGBoost\b|hotspot[\s._-]?risk|\bmodel\b|\bprediction\b|\bclassifier\b|\bMobileNet\b|\bGEE\b|\btraining\b|\bensemble\b|\bNEA\b|\brainfall\b|\bweather\b|Open[\s.-]?Meteo|\bcalibration\b|\bprecipitation\b|\bmachine\s+learning\b|\bML\b/i,
  },
  {
    agent: 'maps-geo',
    keywords: /\bMapLibre\b|map[\s._-]?layer|\bPostGIS\b|\bGeoJSON\b|\broute\b|\bPMTiles\b|\binundation\b|\bspatial\b|\bcoordinates?\b|\bbounding\s+box\b|\bMRT\b|\bmetro\b/i,
  },
  {
    agent: 'frontend-ui',
    keywords: /\bReact\b|\bcomponent\b|\bscreen\b|\bdialog\b|\bmodal\b|\bTailwind\b|\bhook\b|\bcontext\b|\bRadix\b|\bPWA\b|\bonboarding\b|\bUI\b|\bCSS\b|\blayout\b|\bresponsive\b/i,
  },
  {
    agent: 'backend-api',
    keywords: /\bFastAPI\b|\bendpoint\b|\bservice\b|\bSQLAlchemy\b|\bPydantic\b|\bAPI\b|\brouter\b|\bmiddleware\b|\balert\b|\bIMD\b|\bCWC\b|\bGDACS\b|\bGDELT\b|\bTelegram\b|\bfetcher\b|\bscraper\b|safety[\s._-]?circle|\bWhatsApp\b|\bTwilio\b|\bMeta\b|\bwebhook\b|\btemplate\b|\bgamification\b|\bbadge\b|\bleaderboard\b/i,
  },
];

// --- Danger Signals ---

const dangerSignals = [
  { pattern: /\bdrop\b/i, category: 'Database', detail: '"drop" detected — check if destructive DB operation' },
  { pattern: /delete\s+table/i, category: 'Database', detail: '"delete table" — ensure migration + rollback plan' },
  { pattern: /\btruncate\b/i, category: 'Database', detail: '"truncate" — irreversible data loss' },
  { pattern: /alter\s+column/i, category: 'Database', detail: '"alter column" — check backward compatibility' },
  { pattern: /remove\s+column/i, category: 'Database', detail: '"remove column" — ensure migration exists' },
  { pattern: /change\s+auth/i, category: 'Auth', detail: 'Auth change — read auth_service.py + AuthContext.tsx first' },
  { pattern: /modify\s+token/i, category: 'Auth', detail: 'Token modification — read token-storage.ts first' },
  { pattern: /update\s+jwt/i, category: 'Auth', detail: 'JWT change — check all token validation paths' },
  { pattern: /change\s+password/i, category: 'Auth', detail: 'Password logic change — security review required' },
  { pattern: /reset\s+--hard/i, category: 'Destructive', detail: '"reset --hard" — will lose uncommitted work' },
  { pattern: /force\s+push/i, category: 'Destructive', detail: '"force push" — may overwrite remote history' },
  { pattern: /rm\s+-rf/i, category: 'Destructive', detail: '"rm -rf" — irreversible file deletion' },
  { pattern: /delete\s+branch/i, category: 'Destructive', detail: '"delete branch" — verify branch is fully merged' },
];

// --- Main Logic ---

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  try {
    const data = JSON.parse(input);
    const prompt = (data.prompt || '').toString();

    // Skip empty or very short prompts
    if (prompt.trim().length < 3) {
      process.exit(0);
    }

    // Cap at 2000 chars for performance — all regex matching uses this
    const scanText = prompt.substring(0, 2000);
    const output = [];

    // 1. Complexity scoring
    let score = 0;
    const signals = [];
    for (const { pattern, weight, label } of complexityPatterns) {
      if (pattern.test(scanText)) {
        score += weight;
        signals.push(`${label} (${weight > 0 ? '+' : ''}${weight})`);
      }
    }
    score = Math.max(0, score);
    const mode = score >= 3 ? 'DELIBERATE' : 'REFLEXIVE';

    if (score > 0 || signals.length > 0) {
      output.push(`[HOOKS:TRIAGE] Mode: ${mode} (score: ${score})`);
      if (signals.length > 0) {
        output.push(`  Signals: ${signals.join(', ')}`);
      }
      if (mode === 'DELIBERATE') {
        output.push('  -> Full analysis required. Plan before implementing. Use explore agents first.');
      }
    }

    // 2. Domain routing
    const agents = [];
    for (const { agent, keywords } of domainRoutes) {
      if (keywords.test(scanText)) {
        agents.push(agent);
      }
    }
    if (agents.length > 0) {
      output.push(`[HOOKS:ROUTE] Suggested agents: ${agents.join(', ')}`);
    }

    // 3. Danger signals
    const dangers = [];
    for (const { pattern, category, detail } of dangerSignals) {
      if (pattern.test(scanText)) {
        dangers.push({ category, detail });
      }
    }
    if (dangers.length > 0) {
      for (const d of dangers) {
        output.push(`[HOOKS:DANGER] ${d.category}: ${d.detail}`);
      }
    }

    // 4. Reflection feedback loop
    try {
      const reflectionsPath = path.join(__dirname, 'reflections.jsonl');
      const stat = fs.statSync(reflectionsPath);

      if (stat.size > 0 && stat.size <= 50000) {
        // Read the file (capped at 10KB for matching, read from end if large)
        let content;
        if (stat.size <= 10240) {
          content = fs.readFileSync(reflectionsPath, 'utf8');
        } else {
          const fd = fs.openSync(reflectionsPath, 'r');
          try {
            const buffer = Buffer.alloc(10240);
            fs.readSync(fd, buffer, 0, 10240, stat.size - 10240);
            content = buffer.toString('utf8');
          } finally {
            fs.closeSync(fd);
          }
        }

        const lines = content.split('\n').filter(l => l.trim());
        const scanLower = scanText.toLowerCase();
        const scored = [];

        for (const line of lines) {
          try {
            const reflection = JSON.parse(line);
            if (!reflection.tags || !Array.isArray(reflection.tags)) continue;

            let matchCount = 0;
            for (const tag of reflection.tags) {
              if (scanLower.includes(tag.toLowerCase())) {
                matchCount++;
              }
            }
            if (matchCount > 0) {
              scored.push({ reflection, matchCount });
            }
          } catch (e) {
            // Skip malformed lines
          }
        }

        // Sort by match count, take top 3
        scored.sort((a, b) => b.matchCount - a.matchCount);
        const top = scored.slice(0, 3);

        if (top.length > 0) {
          output.push('[HOOKS:MEMORY] Relevant past reflections:');
          for (let i = 0; i < top.length; i++) {
            const r = top[i].reflection;
            const tags = (r.tags || []).map(t => `#${t}`).join(', ');
            output.push(`  ${i + 1}. [${r.date || '?'}] ${r.reflection || r.message || '(no text)'} (${tags})`);
          }
        }
      }
    } catch (e) {
      // Reflections file doesn't exist or unreadable — skip silently
    }

    // 5. Active plan surfacing (anti-compaction)
    try {
      const sessionFile = path.join(__dirname, 'session-changes.json');
      const sessionData = JSON.parse(fs.readFileSync(sessionFile, 'utf8'));
      if (sessionData.active_plan && sessionData.active_plan.path) {
        const planPath = sessionData.active_plan.absolute_path || sessionData.active_plan.path;
        output.push(`[HOOKS:PLAN] Active plan: ${planPath}`);
        output.push(`  If context was compacted, re-read this file before implementing.`);
      }
    } catch (e) {
      // No session file or no active plan — skip
    }

    // Output only if there's something useful
    if (output.length > 0) {
      console.log(output.join('\n'));
    }

  } catch (e) {
    // JSON parse error — skip silently, don't block the prompt
  }
  process.exit(0);
});
