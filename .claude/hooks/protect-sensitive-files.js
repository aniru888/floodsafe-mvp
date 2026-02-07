/**
 * PreToolUse hook: Blocks Edit/Write to sensitive files (.env, credentials, secrets)
 *
 * Input: JSON on stdin with tool_name and tool_input.file_path
 * Output: JSON on stdout with permissionDecision: "deny" to block
 * Exit 0 = allow (unless JSON says deny), Exit 2 = block
 */

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  try {
    const data = JSON.parse(input);
    const filePath = (data.tool_input && data.tool_input.file_path) || '';

    // Patterns to block (excluding FloodSafe project .env files)
    const blocked = /[/\\]\.env$|[/\\]\.env\.|credentials|secrets|\.pem$|\.key$/i;
    const allowlisted = /FloodSafe[/\\]apps[/\\][^/\\]+[/\\]\.env$/i;

    if (blocked.test(filePath) && !allowlisted.test(filePath)) {
      console.log(JSON.stringify({
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "deny",
          permissionDecisionReason: `BLOCKED: ${filePath} is a sensitive file. Edit it manually to prevent credential exposure.`
        }
      }));
    }
  } catch (e) {
    // Parse error — allow the action (non-blocking)
  }
  process.exit(0);
});
