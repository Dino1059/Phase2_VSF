export interface GuardScanResult {
  safe: boolean;
  flags: string[];
}

const INJECTION_PATTERNS: Array<{ name: string; regex: RegExp }> = [
  { name: 'ignore_instructions', regex: /ignore (all )?(previous|prior) instructions/i },
  { name: 'system_prompt_exfiltration', regex: /system prompt.*(reveal|show|print|exfiltrate)|(reveal|show|print|exfiltrate).*(system prompt)/i },
  { name: 'disregard_rules', regex: /disregard .{0,20}(rules|guardrails|instructions)/i },
  { name: 'role_switch', regex: /you are now/i },
  { name: 'jailbreak', regex: /\bDAN\b|jailbreak/i },
  { name: 'sql_injection', regex: /drop\s+table|;--/i },
];

export function scanInput(text: string): GuardScanResult {
  if (!text) return { safe: true, flags: [] };
  const flags: string[] = [];
  for (const item of INJECTION_PATTERNS) {
    if (item.regex.test(text)) {
      flags.push(item.name);
    }
  }
  return {
    safe: flags.length === 0,
    flags,
  };
}

export function scanRenderable(text: string): GuardScanResult {
  return scanInput(text);
}
