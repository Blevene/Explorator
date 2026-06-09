import { useState } from 'react';
import { listArrangements, getArrangement, triggerRealizationSSE } from '../services/api';
import type { FinalSelection } from '../services/api';
import { useArrangementStore } from '../stores/arrangementStore';
import { useCandidateStore } from '../stores/candidateStore';
import { streamSSE, SSETimeoutError } from './streamSSE';

/** Outcome of a realization attempt; `error` carries the reason on failure. */
export type RealizeResult =
  | { status: 'cached' | 'realized' }
  | { status: 'error'; error: string };

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

  const realize = async (candidateId: string): Promise<RealizeResult> => {
    if (!sessionId) return { status: 'error', error: 'No active session' };

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
        return { status: 'cached' };
      }
    } catch { /* no cache */ }

    // Trigger realization
    arrangementStore.reset();
    setCurrentNode('load_context');
    setLoading(true);

    try {
      // Bounded by an AbortController + timeout via streamSSE, so a stream that
      // opens then hangs with zero bytes can't leave realization stuck loading.
      await streamSSE({
        open: (signal) => triggerRealizationSSE(sessionId, [candidateId], signal),
        notOkMessage: (status) => `Realization failed: ${status}`,
        onEvent: ({ event: eventType, data }) => {
          const node = data.node as string | undefined;
          if (eventType === 'node_started' && node) setCurrentNode(node);
          else if (eventType === 'realization_completed') setCurrentNode(null);
        },
      });

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
      return { status: 'realized' };
    } catch (err) {
      // Surface the real reason so a timeout is distinguishable from a 500.
      const error = err instanceof SSETimeoutError
        ? 'Realization timed out after 10 minutes.'
        : err instanceof Error
          ? err.message
          : 'Realization failed';
      return { status: 'error', error };
    } finally {
      setLoading(false);
      setCurrentNode(null);
    }
  };

  return { loading, currentNode, realize, selectArrangement };
}
