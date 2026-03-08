/**
 * PostToolUse hook (Bash): Commit Reflector
 *
 * Detects git commit commands and outputs a structured reflection prompt
 * that instructs Claude to capture lessons learned.
 *
 * The hook does NOT write reflections itself — it instructs Claude to do so,
 * because only Claude can generate the actual reflection text.
 *
 * Input: JSON on stdin with { tool_name, tool_input: { command }, tool_response, session_id }
 * Output: JSON on stdout with hookSpecificOutput.additionalContext (PostToolUse requires JSON format)
 */

// --- Domain tag extraction from commit message ---

const tagPatterns = [
  { pattern: /\bFHI\b|\brainfall\b|\bweather\b|\bNEA\b|\bcalibration\b/i, tag: 'FHI' },
  { pattern: /\bhotspot\b|\bXGBoost\b|\brisk\b/i, tag: 'hotspots' },
  { pattern: /\bauth\b|\blogin\b|\btoken\b|\bJWT\b/i, tag: 'auth' },
  { pattern: /\bmap\b|\bMapLibre\b|\bGeoJSON\b|\blayer\b|\bspatial\b/i, tag: 'maps' },
  { pattern: /\breport\b|\bphoto\b|\bverif/i, tag: 'reports' },
  { pattern: /\balert\b|\bIMD\b|\bGDACS\b|\bfetch/i, tag: 'alerts' },
  { pattern: /\bWhatsApp\b|\bTwilio\b|\bMeta\b|\bwebhook\b/i, tag: 'whatsapp' },
  { pattern: /\bcircle\b|\binvite\b|\bmember\b/i, tag: 'circles' },
  { pattern: /\bgamif\b|\bbadge\b|\bleaderboard\b|\bstreak\b/i, tag: 'gamification' },
  { pattern: /\broute\b|\bnavigat/i, tag: 'routing' },
  { pattern: /\bPWA\b|\bservice.worker\b|\boffline\b/i, tag: 'pwa' },
  { pattern: /\bonboard/i, tag: 'onboarding' },
  { pattern: /\bmodel\b|\bML\b|\bclassif/i, tag: 'ml' },
  { pattern: /\bschema\b|\bmigrat\b|\bdatabase\b|\bPostGIS\b/i, tag: 'database' },
  { pattern: /\bconfig\b|\benv\b|\bdeploy/i, tag: 'config' },
  { pattern: /\btest\b|\bpytest\b|\bspec\b/i, tag: 'testing' },
  { pattern: /\bfront/i, tag: 'frontend' },
  { pattern: /\bback/i, tag: 'backend' },
  { pattern: /\bsensor\b|\bIoT\b|\bESP32\b/i, tag: 'iot' },
  { pattern: /\bsearch\b|\bNominatim\b|\bgeocode\b/i, tag: 'search' },
];

// Conventional commit type → tag
const commitTypeMap = {
  'fix': 'bugfix',
  'feat': 'feature',
  'refactor': 'refactor',
  'docs': 'docs',
  'test': 'testing',
  'chore': 'chore',
  'perf': 'performance',
  'style': 'style',
};

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  try {
    const data = JSON.parse(input);
    const command = (data.tool_input && data.tool_input.command) || '';
    const response = data.tool_response || {};

    // Only fire on git commit (not amend, not allow-empty)
    if (!/git\s+commit\b/i.test(command)) {
      process.exit(0);
    }
    if (/--amend/i.test(command) || /--allow-empty/i.test(command)) {
      process.exit(0);
    }

    // Check if commit succeeded
    const stdout = (response.stdout || '').toString();
    const exitCode = response.exit_code !== undefined ? response.exit_code : null;

    // Only skip if exit code is definitively non-zero
    if (exitCode !== null && exitCode !== 0) {
      process.exit(0);
    }

    // Extract commit message
    let commitMsg = '';
    // Try -m "message" or -m 'message'
    const mMatch = command.match(/-m\s+["']([^"']+)["']/);
    if (mMatch) {
      commitMsg = mMatch[1];
    } else {
      // Try heredoc pattern: cat <<'EOF' ... EOF
      const heredocMatch = command.match(/<<'?EOF'?\s*\n([\s\S]*?)\nEOF/);
      if (heredocMatch) {
        commitMsg = heredocMatch[1].trim().split('\n')[0]; // First line
      }
    }

    // Extract commit hash from output
    let commitHash = '';
    const hashMatch = stdout.match(/\[[\w/.-]+\s+([a-f0-9]{7,})\]/);
    if (hashMatch) {
      commitHash = hashMatch[1];
    }

    // Derive domain tags
    const tags = [];
    const textToScan = (commitMsg + ' ' + stdout).toLowerCase();

    // Check commit type prefix (fix:, feat:, etc.)
    const typeMatch = commitMsg.match(/^(\w+)[:(]/);
    if (typeMatch && commitTypeMap[typeMatch[1].toLowerCase()]) {
      tags.push(commitTypeMap[typeMatch[1].toLowerCase()]);
    }

    // Check domain patterns
    for (const { pattern, tag } of tagPatterns) {
      if (pattern.test(textToScan)) {
        tags.push(tag);
      }
    }

    // Deduplicate tags
    const uniqueTags = [...new Set(tags)];

    // Build today's date
    const today = new Date().toISOString().split('T')[0];

    // Build reflection template — use JSON.stringify for the sample line to avoid escaping issues
    const sampleLine = JSON.stringify({
      date: today,
      commit: commitHash,
      message: commitMsg || '(no message)',
      reflection: 'YOUR_REFLECTION_HERE',
      tags: uniqueTags,
    });

    const context = [
      `[HOOKS:REFLECT] Commit detected: "${commitMsg || '(no message)'}"${commitHash ? ` (${commitHash})` : ''}`,
      '',
      'Reflect briefly on this commit:',
      '1. What was the trickiest part of this change?',
      '2. Any gotcha or non-obvious behavior worth remembering?',
      '3. Would this lesson apply to future similar tasks?',
      '',
      'If worth saving, append ONE JSON line to .claude/hooks/reflections.jsonl:',
      sampleLine,
      '',
      'Skip if this was trivial (typo, comment, import).',
    ].join('\n');

    console.log(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        additionalContext: context,
      }
    }));

  } catch (e) {
    // Parse error — don't block, exit silently
  }
  process.exit(0);
});
