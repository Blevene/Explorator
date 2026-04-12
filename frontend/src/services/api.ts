const API_BASE = '/v1';

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

export async function createSession(prompt: string, mode = 'full_exploration'): Promise<SessionSummary> {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, mode }),
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

export async function triggerRoundSSE(
  sessionId: string,
  prompt: string,
  generationMode: string,
): Promise<Response> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/rounds`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, generation_mode: generationMode }),
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

export interface ArrangementSummary {
  id: string
  status: "draft" | "selected" | "rejected"
  progression_candidate_id: string
  voicing_plan_id: string
  bass_line_id: string
  weighted_total: number
  rank_within_round: number
  rationale: string
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
