export interface TokenUsageBreakdown {
  input: number;
  output: number;
  calls: number;
}

export interface TokenUsage {
  round: number;
  total_input: number;
  total_output: number;
  total_cached: number;
  total_tokens: number;
  by_model: Record<string, { input: number; output: number; cached: number; calls: number }>;
  by_phase: Record<string, TokenUsageBreakdown & { model: string }>;
  estimated_cost_usd: number;
  is_estimate: boolean;
  is_synthetic: boolean;
  /** False when no LLM_PRICE_* is configured (e.g. local models). Absent on pre-012 events. */
  is_priced?: boolean;
  /** LLM calls per node that failed (results defaulted or dropped). */
  fallbacks?: Record<string, number>;
}
