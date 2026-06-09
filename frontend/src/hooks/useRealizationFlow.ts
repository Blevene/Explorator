import { useState, useRef, useEffect } from 'react';
import { listArrangements, getArrangement, triggerRealizationSSE } from '../services/api';
import type { FinalSelection } from '../services/api';
import { useArrangementStore } from '../stores/arrangementStore';
import { useCandidateStore } from '../stores/candidateStore';
import { streamSSE, SSETimeoutError, USER_ABORT } from './streamSSE';

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
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  const arrangementStore = useArrangementStore();

  // Track mount status so post-await / `finally` setState calls can be gated:
  // a caller abort fired from the unmount cleanup still runs `finally`, which
  // would otherwise update state on an unmounted (dead) fiber.
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Abort any in-flight realization on unmount / session change. Aborting closes
  // the client request; the backend cancels the in-flight round on disconnect
  // (best-effort), instead of leaking it until the timeout fires.
  useEffect(() => {
    return () => abortRef.current?.abort(USER_ABORT);
  }, [sessionId]);

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

    // Abort any prior in-flight controller before replacing it, so a re-entrant
    // call can't orphan a stream that's then only abortable by the timeout.
    abortRef.current?.abort(USER_ABORT);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      // Bounded by an AbortController + timeout via streamSSE, so a stream that
      // opens then hangs with zero bytes can't leave realization stuck loading.
      await streamSSE({
        signal: controller.signal,
        open: (signal) => triggerRealizationSSE(sessionId, [candidateId], signal),
        notOkMessage: (status) => `Realization failed: ${status}`,
        onEvent: ({ event: eventType, data }) => {
          const node = data.node as string | undefined;
          if (eventType === 'node_started' && node) setCurrentNode(node);
          else if (eventType === 'realization_completed') setCurrentNode(null);
          // The backend emits realization_error over a 200 stream. Without this
          // the stream would end normally and we'd return {status:'realized'}
          // with empty arrangements — silently swallowing the failure. Throw so
          // it propagates through streamSSE into the catch → {status:'error'}.
          else if (eventType === 'realization_error') {
            throw new Error((data.error as string) ?? 'Realization failed');
          }
        },
      });

      const arrangements = await listArrangements(candidateId);
      // Unmounted mid-flight (caller abort): skip the post-await state writes.
      if (!mountedRef.current) return { status: 'realized' };
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
      // A caller-driven abort (unmount / session change) isn't a failure to report.
      if (controller.signal.aborted && !(err instanceof SSETimeoutError)) {
        return { status: 'error', error: 'Realization cancelled' };
      }
      // Surface the real reason so a timeout is distinguishable from a 500.
      const error = err instanceof SSETimeoutError
        ? 'Realization timed out after 10 minutes.'
        : err instanceof Error
          ? err.message
          : 'Realization failed';
      return { status: 'error', error };
    } finally {
      // Ref reset is unconditional (not state). The state resets are gated on
      // mount: a caller abort fired from unmount cleanup still runs `finally`,
      // and updating state on a dead fiber is a no-op bug. Normal completion
      // runs with mountedRef.current === true, so loading still resets.
      if (abortRef.current === controller) abortRef.current = null;
      if (mountedRef.current) {
        setLoading(false);
        setCurrentNode(null);
      }
    }
  };

  return { loading, currentNode, realize, selectArrangement };
}
