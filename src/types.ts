// types.ts — ترجمة مباشرة لمخطط scenario_generator.py (البنية والقيم كما هي)

export interface Env {
  MARSAD_KV: KVNamespace;
  DEEPSEEK_API_KEY?: string;
  GROQ_API_KEY?: string;
  OPENROUTER_API_KEY?: string;
  GOOGLE_API_KEY?: string;
  HF_API_KEY?: string;
  E2B_API_KEY: string;
  RAILWAY_INGEST_URL?: string;
}

export const TIER_MIN_FILES: Record<number, number> = { 1: 1, 2: 2, 3: 3, 4: 4, 5: 5 };
export const TIER_MIN_DEPS: Record<number, number> = { 1: 0, 2: 1, 3: 1, 4: 2, 5: 2 };
export const MAX_TIER = 5;

export function tierRequiresAuthLayer(tier: number): boolean {
  return tier >= 2;
}
export function tierRequiresMultiStepDefect(tier: number): boolean {
  return tier >= 4;
}

// فئات "خطأ منطقي شائع" — نفس القائمة حرفياً من scenario_generator.py
export const LOGIC_DEFECT_CLASSES = [
  "missing_role_check",
  "missing_ownership_check",
  "stale_permission_cache",
  "incorrect_boolean_logic_in_authorization",
  "missing_null_check_before_sensitive_action",
  "race_condition_in_state_update",
  "improper_default_value_grants_access",
  "missing_rate_or_quota_check",
  "inconsistent_validation_between_layers",
  "off_by_one_in_access_boundary",
] as const;

export type DefectClass = (typeof LOGIC_DEFECT_CLASSES)[number];

export const TECH_STACKS: [string, string, string][] = [
  ["python", "fastapi", "postgres"],
  ["python", "flask", "redis"],
  ["node", "express", "mongodb"],
  ["go", "gin", "postgres"],
  ["python", "django", "postgres"],
];

export const FORBIDDEN_PATTERNS = [
  "hello_world", "single_route_app", "no_persistence_layer",
  "exploit", "payload", "attack_string", "shell_injection",
  "reverse_shell", "sql_injection_payload",
];

export interface ScenarioBlueprint {
  scenarioId: string;
  tier: number;
  defectClass: DefectClass;
  stack: [string, string, string];
  minFiles: number;
  minRealDependencies: number;
  requiresAuthLayer: boolean;
  requiresMultiStepDefect: boolean;
  narrativeBrief: string;
  forbiddenPatterns: string[];
}

export interface AgentProgress {
  agentId: string;
  tier: number;
  consecutiveSuccesses: number;
  consecutiveFailures: number;
  totalRounds: number;
}

export interface ProjectArtifact {
  scenarioId: string;
  providerUsed: string;
  baseCode: Record<string, string>;
  verificationTest: string;
  patchedCode: Record<string, string>;
  rawResponseChars: number;
}

export interface RoundData {
  source: "e2b_agent";
  defect_class: string;
  base_code: Record<string, string>;
  verification_test: string;
  patched_code: Record<string, string> | null;
  execution_log: string;
  defect_confirmed: boolean;
  fix_verified: boolean;
  regression_passed: boolean;
  attempt_count: number;
  time_to_fix_seconds: number;
  sandbox_id: string;
}
