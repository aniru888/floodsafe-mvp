/**
 * PostToolUse hook (Edit|Write): Change Tracker with Hybrid Review
 *
 * Two modes:
 * - Light mode (most files): Silent tracking, warns at thresholds (5/10/15 files)
 * - Full review mode (critical files): 4-phase review chain instruction
 *
 * Tracks all file modifications in session-changes.json (resets per session).
 *
 * Input: JSON on stdin with { tool_name, tool_input: { file_path }, session_id, cwd }
 * Output: JSON on stdout with hookSpecificOutput.additionalContext (only when warnings needed)
 */

const fs = require('fs');
const path = require('path');

// --- Critical File Patterns (from CLAUDE.md safety rules) ---

const criticalFiles = [
  { pattern: /infrastructure[/\\]models\.py$/i, reason: 'DB schema — ensure migration script exists' },
  { pattern: /auth_service\.py$/i, reason: 'Auth flows — check all auth paths still work' },
  { pattern: /AuthContext\.tsx$/i, reason: 'Auth context — verify login/logout/register flows' },
  { pattern: /token-storage\.ts$/i, reason: 'Token handling — check token refresh + storage' },
  { pattern: /core[/\\]config\.py$/i, reason: 'Environment config — verify all env vars documented' },
  { pattern: /settings\.local\.json$/i, reason: 'Claude settings — hooks and permissions' },
  { pattern: /main\.py$/i, reason: 'App entrypoint — check startup + middleware chain' },
  { pattern: /vite\.config/i, reason: 'Build config — verify build still passes' },
];

// --- File Category Detection ---

function categorize(filePath) {
  const fp = filePath.replace(/\\/g, '/').toLowerCase();
  if (fp.includes('/apps/frontend/') || ((fp.endsWith('.tsx') || fp.endsWith('.ts') || fp.endsWith('.css')) && fp.includes('frontend')))
    return 'frontend';
  if (fp.includes('/apps/backend/') || (fp.endsWith('.py') && fp.includes('backend')))
    return 'backend';
  if (fp.includes('/apps/ml-service/'))
    return 'ml';
  if (fp.includes('/apps/iot-ingestion/') || fp.includes('/apps/esp32-firmware/'))
    return 'iot';
  if (fp.match(/\.(json|yml|yaml|toml)$/) || fp.includes('/config/') || fp.includes('.env'))
    return 'config';
  if (fp.includes('/test') || fp.includes('/__test') || fp.match(/\.(test|spec)\./))
    return 'test';
  if (fp.endsWith('.md'))
    return 'docs';
  if (fp.includes('/.claude/hooks/'))
    return 'hooks';
  return 'other';
}

// --- Check if file is critical ---

function getCriticalInfo(filePath) {
  for (const { pattern, reason } of criticalFiles) {
    if (pattern.test(filePath)) {
      return reason;
    }
  }
  return null;
}

// --- 4-Phase Review Template ---

function buildReviewPrompt(filePath, reason) {
  const fileName = path.basename(filePath);
  return [
    `[HOOKS:REVIEW] CRITICAL FILE MODIFIED: ${fileName}`,
    `  Reason: ${reason}`,
    '',
    'You MUST complete this 4-phase review before continuing:',
    '',
    'Phase 1 — SIMPLIFY: Is this change minimal? Any unnecessary complexity added?',
    'Phase 2 — SELF-CRITIQUE: What could break? Backward compatibility? Migration needs? Edge cases?',
    'Phase 3 — BUG SCAN: Security issues? Type safety? Null handling? SQL injection? OWASP top 10?',
    'Phase 4 — PROVE IT: What specific command verifies this works? (e.g., pytest, tsc --noEmit, curl)',
    '',
    'Do NOT proceed to the next file edit until all 4 phases are addressed.',
  ].join('\n');
}

// --- Session State Management ---

function loadSession(sessionFile, currentSessionId) {
  try {
    const raw = fs.readFileSync(sessionFile, 'utf8');
    const data = JSON.parse(raw);
    // Reset if session changed
    if (data.session_id !== currentSessionId) {
      return null;
    }
    return data;
  } catch (e) {
    return null;
  }
}

function createSession(sessionId) {
  return {
    session_id: sessionId,
    started_at: new Date().toISOString(),
    changes: [],
    file_set: [],
  };
}

// --- Main Logic ---

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  try {
    const data = JSON.parse(input);
    const sessionId = data.session_id || 'unknown';
    const cwd = data.cwd || process.cwd();

    // Extract file path
    const filePath = (data.tool_input && (data.tool_input.file_path || data.tool_input.filePath)) || '';
    if (!filePath) {
      process.exit(0);
    }

    // Normalize to relative path
    let relativePath = filePath;
    if (path.isAbsolute(filePath)) {
      relativePath = path.relative(cwd, filePath).replace(/\\/g, '/');
    }

    const category = categorize(filePath);
    const criticalReason = getCriticalInfo(filePath);
    const sessionFile = path.join(__dirname, 'session-changes.json');

    // Load or create session
    let session = loadSession(sessionFile, sessionId);
    if (!session) {
      session = createSession(sessionId);
    }

    // Track the change
    const isNewFile = !session.file_set.includes(relativePath);
    if (isNewFile) {
      session.file_set.push(relativePath);
    }
    session.changes.push({
      file_path: relativePath,
      category,
      tool: data.tool_name || 'unknown',
      timestamp: new Date().toISOString(),
      is_critical: !!criticalReason,
    });

    // Cap changes array to prevent unbounded growth
    const MAX_CHANGES = 200;
    if (session.changes.length > MAX_CHANGES) {
      session.changes = session.changes.slice(-MAX_CHANGES);
    }

    // Detect plan/design docs and register as active plan
    const normalizedPath = filePath.replace(/\\/g, '/');
    const isPlanDoc = /\/(docs\/plans|\.claude\/plans)\/.*\.md$/i.test(normalizedPath);
    if (isPlanDoc) {
      session.active_plan = {
        path: relativePath,
        absolute_path: filePath,
        set_at: new Date().toISOString(),
      };
    }

    // Save session state
    try {
      fs.writeFileSync(sessionFile, JSON.stringify(session, null, 2), 'utf8');
    } catch (e) {
      // Can't write session file — continue without tracking
    }

    // --- Determine Output ---

    const output = [];
    const uniqueFileCount = session.file_set.length;

    // Critical file → full 4-phase review
    if (criticalReason) {
      output.push(buildReviewPrompt(filePath, criticalReason));
    }

    // Threshold reminders (only on new unique files crossing threshold)
    if (isNewFile) {
      const thresholds = [15, 10, 5];
      for (const t of thresholds) {
        if (uniqueFileCount === t) {
          // Count by category
          const counts = {};
          for (const fp of session.file_set) {
            const cat = categorize(fp);
            counts[cat] = (counts[cat] || 0) + 1;
          }
          const summary = Object.entries(counts)
            .map(([cat, count]) => `${count} ${cat}`)
            .join(', ');

          output.push(`[HOOKS:TRACKER] ${uniqueFileCount} unique files modified this session (${summary}). Consider running /preflight to verify everything still builds.`);
          break;
        }
      }
    }

    // Output if there's anything to say
    if (output.length > 0) {
      console.log(JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'PostToolUse',
          additionalContext: output.join('\n\n'),
        }
      }));
    }

  } catch (e) {
    // Parse error — don't block, exit silently
  }
  process.exit(0);
});
