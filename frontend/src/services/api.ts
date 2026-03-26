const API_BASE = '/v1';

export interface SessionSummary {
  session_id: string;
  status: string;
  mode: string;
  created_at: string;
  prompt: string;
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
