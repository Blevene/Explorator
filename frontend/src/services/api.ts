const API_BASE = '/v1';

export interface Capabilities {
  persistence_mode: 'neo4j' | 'memory';
  features: Record<string, boolean>;
}

export async function getCapabilities(): Promise<Capabilities> {
  const res = await fetch(`${API_BASE}/capabilities`);
  if (!res.ok) throw new Error(`Failed to fetch capabilities: ${res.status}`);
  return res.json();
}

export interface SessionSummary {
  session_id: string;
  status: string;
  mode: string;
  created_at: string;
  prompt: string;
  genre?: string;
}

export interface SessionListResponse {
  items: SessionSummary[];
}

export interface GenreSummary {
  genre: string;
  display_name: string;
}

export interface GenreListResponse {
  items: GenreSummary[];
}

export async function createSession(
  genre: string,
  prompt = '',
  mode = 'full_exploration',
): Promise<SessionSummary> {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ genre, prompt: prompt ?? '', mode }),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  return res.json();
}

export async function listSessions(): Promise<SessionListResponse> {
  const res = await fetch(`${API_BASE}/sessions`);
  if (!res.ok) throw new Error(`Failed to list sessions: ${res.status}`);
  return res.json();
}

export async function getSession(sessionId: string): Promise<SessionSummary> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`);
  if (!res.ok) throw new Error(`Failed to get session: ${res.status}`);
  return res.json();
}

export async function listGenres(): Promise<GenreListResponse> {
  const res = await fetch(`${API_BASE}/genres`);
  if (!res.ok) throw new Error(`Failed to list genres: ${res.status}`);
  return res.json();
}

/** Convenience wrapper that returns the genre items array directly. */
export async function getGenres(): Promise<GenreSummary[]> {
  const data = await listGenres();
  return data.items;
}

export interface GenreDetail {
  genre: string;
  display_name?: string;
  subgenre?: string | null;
  version?: number;
  harmonic_vocabulary?: string[];
  harmonic_tendencies?: Record<string, string>;
  voicing_tendencies?: Record<string, string>;
  bass_tendencies?: Record<string, string>;
  groove_tendencies?: Record<string, string>;
  melodic_tendencies?: Record<string, string>;
  common_devices?: string[];
  anti_patterns?: string[];
  experimentation_envelope?: Record<string, number>;
  voicing_preferences?: Record<string, unknown>;
  bass_preferences?: Record<string, unknown>;
  // Backend may surface arbitrary extra fields (timestamps, melodic_tendencies, ids).
  // Consumers index those via `(g as Record<string, unknown>)[key]` when needed.
}

export async function getGenreDetail(genreName: string): Promise<GenreDetail> {
  const res = await fetch(`${API_BASE}/genres/${genreName}`);
  if (!res.ok) throw new Error(`Failed to get genre: ${res.status}`);
  return res.json();
}

export interface CandidateSummary {
  candidate_id: string;
  type: string;
  status: string;
  key_center: string;
  mode: string;
  chord_symbols: string[];
  roman_numerals: string[];
  rationale: string;
  intent_tags: string[];
  weighted_total: number;
  scores: Record<string, number>;
  metadata?: Record<string, unknown>;
}

export interface CandidateListResponse {
  items: CandidateSummary[];
}

export async function listCandidates(sessionId: string): Promise<CandidateListResponse> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/candidates`);
  if (!res.ok) throw new Error(`Failed to list candidates: ${res.status}`);
  return res.json();
}

export async function dismissCandidate(candidateId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/candidates/${candidateId}/dismiss`, { method: 'PATCH' });
  if (!res.ok) throw new Error(`Failed to dismiss candidate: ${res.status}`);
}

export async function triggerRoundSSE(
  sessionId: string,
  prompt?: string,
  genre?: string,
): Promise<Response> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/rounds`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, genre }),
  });
  if (!res.ok) throw new Error(`Failed to trigger round: ${res.status}`);
  return res;
}

// --- M2c Arrangement Types ---

export interface VoicingEvent {
  bar: number
  beat: number
  duration_beats: number
  pitches: string[]
  chord_symbol: string
}

export interface BassNoteEvent {
  bar: number
  beat: number
  duration_beats: number
  pitch: string
  velocity: number
}

export interface GrooveEvent {
  beat: number
  duration_beats: number
  velocity: number
  accent: boolean
}

export interface ArrangementSummary {
  id: string
  status: "draft" | "selected" | "rejected"
  progression_candidate_id: string
  voicing_plan_id: string
  bass_line_id: string
  weighted_total: number
  rank_within_round: number
  rationale: string
  // M5d-3: null = arrangement not yet harvested into library;
  //        false/true = explicit user curation state.
  // Mandatory nullable (not optional) — the backend always emits these fields.
  is_curated: boolean | null
  curated_at: string | null
}

export interface ArrangementDetail extends ArrangementSummary {
  voicing_plan: {
    global_strategy: string
    density_level: string
    register_profile: string
    voicing_events: VoicingEvent[]
  } | null
  bass_line: {
    style_mode: string
    note_events: BassNoteEvent[]
  } | null
  groove_pattern: {
    time_signature: string
    swing_amount: number
    density: number
    pattern_events: GrooveEvent[]
    source_template: string
  } | null
  melodic_complement: {
    note_events: { bar: number; beat: number; duration_beats: number; pitch: string; velocity: number }[]
    range_low: string
    range_high: string
    contour_type: string
  } | null
  scorecard?: {
    scores: Record<string, number>
    weighted_total: number
    rank_within_round: number
  }
}

export async function listArrangements(candidateId: string): Promise<ArrangementSummary[]> {
  const res = await fetch(`${API_BASE}/candidates/${candidateId}/arrangements`)
  if (!res.ok) throw new Error(`Failed to list arrangements: ${res.status}`)
  return res.json()
}

export async function getArrangement(arrangementId: string): Promise<ArrangementDetail> {
  const res = await fetch(`${API_BASE}/arrangements/${arrangementId}`)
  if (!res.ok) throw new Error(`Failed to get arrangement: ${res.status}`)
  return res.json()
}

export async function triggerRealizationSSE(
  sessionId: string,
  progressionCandidateIds: string[],
): Promise<Response> {
  return fetch(`${API_BASE}/sessions/${sessionId}/realization-rounds`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ progression_candidate_ids: progressionCandidateIds }),
  })
}

export async function triggerMutation(
  sessionId: string,
  candidateIds: string[],
  guidance?: string,
): Promise<Response> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/mutate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      candidate_ids: candidateIds,
      guidance: guidance || null,
    }),
  });
  if (!res.ok) {
    if (res.status === 409) throw new Error('A mutation is already in progress');
    throw new Error(`Mutation failed: ${res.status}`);
  }
  return res;
}

// --- M3c Finalist Types ---

export interface FinalSelection {
  selected_candidate_ids: string[];
  selection_roles: Record<string, string>;
  selection_notes: string[];
}

// --- M4a Export Types ---

export interface ExportArtifact {
  id: string;
  filename: string;
  artifact_type: string;
}

export interface ExportPackage {
  id: string;
  session_id: string;
  included_candidate_ids: string[];
  formats: string[];
  artifacts: ExportArtifact[];
}

export async function createExportPackage(
  sessionId: string,
  arrangementCandidateIds: string[],
  formats: string[],
): Promise<ExportPackage> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ arrangement_candidate_ids: arrangementCandidateIds, formats }),
  });
  if (!res.ok) throw new Error(`Export failed: ${res.statusText}`);
  return res.json();
}

export async function listExportPackages(sessionId: string): Promise<ExportPackage[]> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/exports`);
  if (!res.ok) throw new Error(`Failed to list exports: ${res.statusText}`);
  return res.json();
}

export function getArtifactDownloadUrl(packageId: string, artifactId: string): string {
  return `${API_BASE}/exports/${packageId}/artifacts/${artifactId}/download`;
}

// --- M4b Explanation Types ---

export interface CandidateExplanation {
  summary: string;
  why_it_works: string[];
  what_is_experimental: string[];
  recommended_use_cases: string[];
}

export async function generateExplanation(candidateId: string): Promise<CandidateExplanation> {
  const res = await fetch(`${API_BASE}/candidates/${candidateId}/explain`, {
    method: 'POST',
  });
  if (res.status === 504) throw new Error('Explanation generation timed out. Try again.');
  if (!res.ok) throw new Error(`Explanation failed: ${res.statusText}`);
  return res.json();
}

export async function getCachedExplanation(candidateId: string): Promise<CandidateExplanation | null> {
  const res = await fetch(`${API_BASE}/candidates/${candidateId}/explanation`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to get explanation: ${res.statusText}`);
  return res.json();
}

// --- Genre Research ---

export interface GenreResearchJob {
  id: string;
  genre_name: string;
  reference_artists: string[];
  status: string;
  research_log: string;
  critique_trail: unknown[];
  // Pre-validation YAML payload from the LLM — shape isn't guaranteed yet,
  // so consumers do their own optional-chaining. Typed as `any` deliberately.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  draft_yamls: Record<string, any>;
  validation_errors?: string[];
  rejection_reason?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DraftSummary {
  job_id: string;
  genre_name: string;
  created_at: string;
}

export interface DraftListResponse {
  items: DraftSummary[];
}

export async function startGenreResearch(
  genreName: string,
  referenceArtists: string[] = [],
): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/genres/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ genre_name: genreName, reference_artists: referenceArtists }),
  });
  if (res.status === 409) {
    const data = await res.json();
    throw new Error(data.detail || 'Genre already exists or research in progress');
  }
  if (!res.ok) throw new Error(`Failed to start research: ${res.status}`);
  return res.json();
}

export async function getResearchStatus(jobId: string): Promise<GenreResearchJob> {
  const res = await fetch(`${API_BASE}/genres/research/${jobId}`);
  if (!res.ok) throw new Error(`Failed to get research status: ${res.status}`);
  return res.json();
}

export function streamResearchProgress(jobId: string): EventSource {
  return new EventSource(`${API_BASE}/genres/research/${jobId}/stream`);
}

export async function listPendingDrafts(): Promise<DraftListResponse> {
  const res = await fetch(`${API_BASE}/genres/drafts`);
  if (!res.ok) throw new Error(`Failed to list drafts: ${res.status}`);
  return res.json();
}

export async function getDraftDetail(jobId: string): Promise<GenreResearchJob> {
  const res = await fetch(`${API_BASE}/genres/drafts/${jobId}`);
  if (!res.ok) throw new Error(`Failed to get draft: ${res.status}`);
  return res.json();
}

export async function approveDraft(jobId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/genres/drafts/${jobId}/approve`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to approve: ${res.status}`);
}

export async function rejectDraft(jobId: string, reason = ''): Promise<void> {
  const res = await fetch(`${API_BASE}/genres/drafts/${jobId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw new Error(`Failed to reject: ${res.status}`);
}

// --- M4b Comparison + Provenance ---

export async function recordComparison(
  sessionId: string,
  candidateIds: string[],
  comparisonAxes: string[],
  labels: Record<string, string>,
): Promise<void> {
  fetch(`${API_BASE}/sessions/${sessionId}/comparisons`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_ids: candidateIds, comparison_axes: comparisonAxes, labels }),
  }).catch(() => {}); // fire-and-forget
}

export interface ProvenanceEvent {
  timestamp: string;
  action: string;
  object_id: string;
  round_number: number | null;
  details: Record<string, unknown>;
}

export async function getProvenance(sessionId: string): Promise<{ session_id: string; events: ProvenanceEvent[] }> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/provenance`);
  if (!res.ok) throw new Error(`Failed to fetch provenance`);
  return res.json();
}
