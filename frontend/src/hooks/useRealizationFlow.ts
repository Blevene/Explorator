import { useState } from 'react';
import { listArrangements, getArrangement, triggerRealizationSSE } from '../services/api';
import type { FinalSelection } from '../services/api';
import { useArrangementStore } from '../stores/arrangementStore';
import { useCandidateStore } from '../stores/candidateStore';

/**
 * Reconstruct finalSelection from arrangement metadata roles.
 * Each arrangement may have metadata.role stamped by persist_realization.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function reconstructFinalSelection(arrangements: any[]): FinalSelection | null {
  const roles: Record<string, string> = {};
  for (const a of arrangements) {
    const meta = typeof a.metadata === 'string' ? JSON.parse(a.metadata || '{}') : (a.metadata ?? {});
    if (meta.role) {
      roles[a.id] = meta.role;
    }
  }
  if (Object.keys(roles).length === 0) return null;
  return {
    selected_candidate_ids: Object.keys(roles),
    selection_roles: roles,
    selection_notes: [],
  };
}

export function useRealizationFlow(sessionId: string | undefined) {
  const [loading, setLoading] = useState(false);
  const [currentNode, setCurrentNode] = useState<string | null>(null);

  const arrangementStore = useArrangementStore();

  const selectArrangement = async (arrangementId: string) => {
    arrangementStore.setSelectedArrangementId(arrangementId);
    const detail = await getArrangement(arrangementId);
    arrangementStore.setSelectedDetail(detail);
  };

  const realize = async (candidateId: string): Promise<'cached' | 'realized' | 'error'> => {
    if (!sessionId) return 'error';

    // Check cache first
    try {
      const existing = await listArrangements(candidateId);
      if (existing.length > 0) {

        arrangementStore.reset();
        arrangementStore.setArrangements(existing);
        // Reconstruct finalist roles from arrangement metadata
        const fs = reconstructFinalSelection(existing);
        if (fs) useCandidateStore.getState().setFinalSelection(fs);
        const best = existing.reduce((a, b) =>
          (a.weighted_total ?? 0) > (b.weighted_total ?? 0) ? a : b
        );
        await selectArrangement(best.id);
        return 'cached';
      }
    } catch { /* no cache */ }

    // Trigger realization
    arrangementStore.reset();
    setCurrentNode('load_context');
    setLoading(true);

    try {
      const response = await triggerRealizationSSE(sessionId, [candidateId]);
      if (!response.ok || !response.body) throw new Error('Realization failed');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split(/\r?\n\r?\n/);
        buffer = parts.pop() || '';

        for (const part of parts) {
          if (!part.trim()) continue;
          let eventType = '';
          let dataStr = '';
          for (const line of part.split(/\r?\n/)) {
            if (line.startsWith('event: ')) eventType = line.slice(7).trim();
            else if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
          }
          if (!dataStr) continue;
          try {
            const data = JSON.parse(dataStr);
            const node = data.node as string | undefined;
            if (eventType === 'node_started' && node) setCurrentNode(node);
            else if (eventType === 'realization_completed') setCurrentNode(null);
          } catch { /* skip */ }
        }
      }

      const arrangements = await listArrangements(candidateId);
      arrangementStore.setArrangements(arrangements);
      // Reconstruct finalist roles from arrangement metadata
      const fs = reconstructFinalSelection(arrangements);
      if (fs) useCandidateStore.getState().setFinalSelection(fs);

      if (arrangements.length > 0) {
        const best = arrangements.reduce((a, b) =>
          (a.weighted_total ?? 0) > (b.weighted_total ?? 0) ? a : b
        );
        await selectArrangement(best.id);
      }
      return 'realized';
    } catch {
      return 'error';
    } finally {
      setLoading(false);
      setCurrentNode(null);
    }
  };

  return { loading, currentNode, realize, selectArrangement };
}
