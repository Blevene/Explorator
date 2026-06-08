import { useState, useCallback, useRef } from 'react';
import { listCandidates } from '../services/api';
import type { FinalSelection } from '../services/api';
import { useCandidateStore } from '../stores/candidateStore';
import { toast } from '../lib/toast';

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

  const { setCandidates, setFinalSelection } = useCandidateStore();

  const generate = useCallback(async (prompt: string, genre?: string) => {
    // A round can run with either a prompt or a selected genre (or both).
    if (!sessionId || loading) return;
    if (!prompt.trim() && !genre) return;

    setLoading(true);
    setCurrentNode(null);
    nodeRef.current = null;
    setError(null);

    // Bound the whole round (including a stream that opens then hangs with no
    // bytes) with an AbortController. `reader.read()` rejects on abort, so a
    // true hang can't block forever and server-side work is cancelled.
    const TIMEOUT_MS = 600_000;
    const controller = new AbortController();
    let timedOut = false;
    const timeoutId = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, TIMEOUT_MS);

    try {
      const response = await fetch(`${API_BASE}/sessions/${sessionId}/rounds`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt.trim(), genre }),
        signal: controller.signal,
      });

      if (!response.ok) throw new Error(`Round failed: ${response.status}`);
      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split(/\r?\n\r?\n/);
          buffer = parts.pop() ?? '';

          for (const part of parts) {
            if (!part.trim()) continue;
            let eventType = '';
            let dataStr = '';
            for (const line of part.split(/\r?\n/)) {
              if (line.startsWith('event: ')) eventType = line.slice(7).trim();
              else if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
            }
            if (!eventType || !dataStr) continue;

            let data: Record<string, unknown>;
            try { data = JSON.parse(dataStr); } catch { continue; }
            const node = data.node as string | undefined;

            if (eventType === 'node_started' && node) {
              nodeRef.current = node;
              setCurrentNode(node);
            } else if (eventType === 'round_completed') {
              nodeRef.current = 'persist_round';
              setCurrentNode('persist_round');
            } else if (eventType === 'round_error') {
              setError((data.error as string) ?? 'Error');
              break;
            } else if (eventType === 'mutation_completed') {
              const mutCount = data.mutations_count as number ?? 0;
              const round = data.round as number ?? 1;
              nodeRef.current = 'mutation_completed';
              setCurrentNode(`mutation_completed:${round}:${mutCount}`);
            } else if (eventType === 'mutation_error') {
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
          }

          await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
        }
      } finally {
        reader.releaseLock();
      }

      try {
        const res = await listCandidates(sessionId);
        setCandidates(res.items);
      } catch {
        setError('Failed to reload candidates after round.');
      }
    } catch (err) {
      if (timedOut) {
        setError('Round timed out after 10 minutes.');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to trigger round.');
      }
    } finally {
      clearTimeout(timeoutId);
      setLoading(false);
      setCurrentNode(null);
    }
  }, [sessionId, loading, setCandidates, setFinalSelection]);

  return { loading, currentNode, error, setError, generate };
}
