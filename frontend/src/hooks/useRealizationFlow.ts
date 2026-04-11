import { useState } from 'react';
import { listArrangements, getArrangement, triggerRealizationSSE } from '../services/api';
import { useArrangementStore } from '../stores/arrangementStore';

export function useRealizationFlow(sessionId: string | undefined) {
  const [loading, setLoading] = useState(false);
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [realizedCandidateIds, setRealizedCandidateIds] = useState<Set<string>>(new Set());

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
        setRealizedCandidateIds(prev => new Set(prev).add(candidateId));
        arrangementStore.reset();
        arrangementStore.setArrangements(existing);
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
      setRealizedCandidateIds(prev => new Set(prev).add(candidateId));
      arrangementStore.setArrangements(arrangements);

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

  return { loading, currentNode, realizedCandidateIds, realize, selectArrangement };
}
