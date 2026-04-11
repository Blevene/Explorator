import { useState } from 'react';
import { triggerMutation, listCandidates } from '../services/api';
import { useCandidateStore } from '../stores/candidateStore';

export interface MutationResult {
  source_id: string;
  mutated_chord_symbols: string[];
  mutations: Array<{
    operation: string;
    position: number;
    original_value: string;
    new_value: string;
    description: string;
  }>;
}

export function useMutationFlow(sessionId: string | undefined) {
  const [mutatingCandidateId, setMutatingCandidateId] = useState<string | null>(null);
  const [inFlight, setInFlight] = useState(false);
  const [inFlightLabel, setInFlightLabel] = useState<string>('');
  const [inFlightChords, setInFlightChords] = useState<string[]>([]);
  const [lastResult, setLastResult] = useState<MutationResult | null>(null);

  const { candidates, setCandidates } = useCandidateStore();

  const LABELS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

  const openModal = (candidateId: string) => setMutatingCandidateId(candidateId);
  const closeModal = () => setMutatingCandidateId(null);

  const mutatingCandidate = candidates.find(c => c.candidate_id === mutatingCandidateId);

  const dismissResult = () => setLastResult(null);

  const submit = async (guidance: string): Promise<string | null> => {
    if (!sessionId || !mutatingCandidateId) return 'No session or candidate';
    const targetId = mutatingCandidateId;
    const idx = candidates.findIndex(c => c.candidate_id === targetId);
    const label = idx >= 0 && idx < LABELS.length ? LABELS[idx] : targetId.slice(0, 8);
    const chords = candidates[idx]?.chord_symbols ?? [];

    setMutatingCandidateId(null);
    setInFlight(true);
    setInFlightLabel(label);
    setInFlightChords(chords);
    setLastResult(null);

    try {
      const response = await triggerMutation(sessionId, [targetId], guidance || undefined);
      if (!response.body) return 'No response body';

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let mutResult: MutationResult | null = null;

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
          try {
            const data = JSON.parse(dataStr);
            if (eventType === 'mutation_completed' && data.results) {
              const r = data.results[0];
              if (r) {
                mutResult = {
                  source_id: r.source_id ?? targetId,
                  mutated_chord_symbols: r.mutated_chord_symbols ?? [],
                  mutations: r.mutations ?? [],
                };
              }
            }
          } catch { /* skip */ }
        }
      }
      reader.releaseLock();

      if (mutResult) setLastResult(mutResult);

      const res = await listCandidates(sessionId);
      setCandidates(res.items);
      return null;
    } catch (err) {
      return err instanceof Error ? err.message : 'Mutation failed';
    } finally {
      setInFlight(false);
    }
  };

  return {
    mutatingCandidateId, mutatingCandidate, inFlight,
    inFlightLabel, inFlightChords, lastResult,
    openModal, closeModal, submit, dismissResult,
  };
}
