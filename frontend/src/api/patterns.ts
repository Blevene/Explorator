import type {
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
  if (filters.curated_only === true) params.set('curated_only', 'true');
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

export async function toggleCuration(
  arrangementId: string,
  curated: boolean,
): Promise<{
  arrangement_id: string;
  is_curated: boolean;
  curated_at: string | null;
  affected_pattern_ids: string[];
}> {
  const res = await fetch(`${API_BASE}/arrangements/${arrangementId}/curation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ curated }),
  });
  if (!res.ok) {
    throw new Error(`toggleCuration ${res.status}: ${await res.text()}`);
  }
  return res.json();
}
