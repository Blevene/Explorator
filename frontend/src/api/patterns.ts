import type {
  HarvestReport,
  PatternCursor,
  PatternFilters,
  PatternItem,
  PatternListResponse,
} from './types';

const API_BASE = '/v1';

export async function listPatterns(
  filters: PatternFilters,
  cursor?: PatternCursor,
  limit = 50,
): Promise<PatternListResponse> {
  const params = new URLSearchParams();
  if (filters.genre) params.set('genre', filters.genre);
  if (filters.pattern_type) params.set('pattern_type', filters.pattern_type);
  if (cursor) {
    params.set('after_score', String(cursor.after_score));
    params.set('after_id', cursor.after_id);
  }
  params.set('limit', String(limit));

  const res = await fetch(`${API_BASE}/patterns?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to list patterns: ${res.status}`);
  return res.json();
}

export async function getPattern(id: string): Promise<PatternItem> {
  const res = await fetch(`${API_BASE}/patterns/${id}`);
  if (!res.ok) throw new Error(`Failed to get pattern: ${res.status}`);
  return res.json();
}

export async function deletePattern(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/patterns/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to delete pattern: ${res.status}`);
}

export async function harvestSessionFinalists(sessionId: string): Promise<HarvestReport> {
  const res = await fetch(
    `${API_BASE}/sessions/${sessionId}/finalists/harvest`,
    { method: 'POST' },
  );
  if (!res.ok) throw new Error(`Failed to harvest finalists: ${res.status}`);
  return res.json();
}
