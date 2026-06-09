import { useState, useCallback, useRef, useEffect } from 'react';
import { listCandidates } from '../services/api';
import type { FinalSelection } from '../services/api';
import { useCandidateStore } from '../stores/candidateStore';
import { toast } from '../lib/toast';
import { streamSSE, STOP_STREAM, SSETimeoutError, USER_ABORT } from './streamSSE';

const API_BASE = '/v1';

export interface GenerationFlowState {
  loading: boolean;
  currentNode: string | null;
  error: string | null;
}

export function useGenerationFlow(sessionId: string | undefined) {
  const [loading, setLoading] = useState(false);
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const nodeRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const { setCandidates, setFinalSelection } = useCandidateStore();

  // Abort any in-flight round on unmount / when the session changes, so we don't
  // leak the request + server work until the 10-minute timeout fires.
  useEffect(() => {
    return () => abortRef.current?.abort(USER_ABORT);
  }, [sessionId]);

  const generate = useCallback(async (prompt: string, genre?: string) => {
    // A round can run with either a prompt or a selected genre (or both).
    if (!sessionId || loading) return;
    if (!prompt.trim() && !genre) return;

    setLoading(true);
    setCurrentNode(null);
    nodeRef.current = null;
    setError(null);

    // Set when the stream reports a terminal error (round_error / mutation_error).
    // Once seen we stop processing AND skip the post-stream candidate reload, so a
    // reload can't clobber the error UX or overwrite the failed-round candidates.
    let streamFailed = false;

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamSSE({
        signal: controller.signal,
        open: (signal) =>
          fetch(`${API_BASE}/sessions/${sessionId}/rounds`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: prompt.trim(), genre }),
            signal,
          }),
        notOkMessage: (status) => `Round failed: ${status}`,
        onEvent: ({ event: eventType, data }) => {
          const node = data.node as string | undefined;

          if (eventType === 'node_started' && node) {
            nodeRef.current = node;
            setCurrentNode(node);
          } else if (eventType === 'round_completed') {
            nodeRef.current = 'persist_round';
            setCurrentNode('persist_round');
          } else if (eventType === 'round_error') {
            setError((data.error as string) ?? 'Error');
            streamFailed = true;
            throw STOP_STREAM;
          } else if (eventType === 'mutation_completed') {
            const mutCount = data.mutations_count as number ?? 0;
            const round = data.round as number ?? 1;
            nodeRef.current = 'mutation_completed';
            setCurrentNode(`mutation_completed:${round}:${mutCount}`);
          } else if (eventType === 'mutation_error') {
            // Non-fatal in the exploration round: a mutation node erroring does
            // not abort the round — it still emits `round_completed` and the
            // post-stream reload pulls whatever candidates were produced. So we
            // surface the error but DON'T set streamFailed / STOP_STREAM, and we
            // let the candidate reload run.
            setError((data.error as string) ?? 'Mutation error');
          } else if (eventType === 'realization_completed') {
            nodeRef.current = 'persist_realization';
            setCurrentNode('persist_realization');
          } else if (eventType === 'node_completed' && node === 'rank_and_select' && data.final_selection) {
            setFinalSelection(data.final_selection as FinalSelection);
          } else if (eventType === 'node_completed' && node === 'harvest_patterns') {
            const count = (data.count as number) ?? 0;
            toast.success(`Saved ${count} patterns to library`);
          }
        },
      });

      // Skip the reload after a terminal stream error so it can't overwrite the
      // real error (or the prior candidates) — and a failed reload won't mask it.
      if (!streamFailed) {
        try {
          const res = await listCandidates(sessionId);
          setCandidates(res.items);
        } catch {
          setError('Failed to reload candidates after round.');
        }
      }
    } catch (err) {
      // A caller-driven abort (unmount / session change) is not a failure to report.
      if (controller.signal.aborted && !(err instanceof SSETimeoutError)) {
        return;
      }
      if (err instanceof SSETimeoutError) {
        setError('Round timed out after 10 minutes.');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to trigger round.');
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setLoading(false);
      setCurrentNode(null);
    }
  }, [sessionId, loading, setCandidates, setFinalSelection]);

  return { loading, currentNode, error, setError, generate };
}
