// Source of truth: backend/src/explorator/services/pattern_library/harvest_service.py
// If the Pydantic dataclass changes, update this file in the same commit.

export type SkipReason =
  | 'missing_arrangement'
  | 'missing_progression'
  | 'missing_genre'
  | 'no_finalists'
  | 'upsert_failed';

export interface SkipEntry {
  candidate_id: string;
  pattern_type: string;
  reason: SkipReason;
}

export interface HarvestReport {
  session_id: string;
  upserted_count: number;
  skipped_count: number;
  skipped_reasons: SkipEntry[];
  upserted_pattern_ids: string[];
}

export interface PatternItem {
  id: string;
  pattern_type: string;
  genre: string;
  tags: string[];
  source_candidate_id: string;
  abstracted_pattern: Record<string, unknown>;
  success_metrics: Record<string, number>;
  notes: string;
  created_at: string;
  is_curated: boolean;
  curated_at: string | null;
}

export interface PatternCursor {
  after_score: number;
  after_id: string;
}

export interface PatternListResponse {
  items: PatternItem[];
  next_cursor: PatternCursor | null;
}

export interface PatternFilters {
  genre?: string;
  pattern_type?: string;
  curated_only?: boolean;
}
