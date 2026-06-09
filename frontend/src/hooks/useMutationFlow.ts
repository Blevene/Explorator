import { useState } from 'react';
import { triggerMutation, listCandidates } from '../services/api';
import { useCandidateStore } from '../stores/candidateStore';
import { streamSSE, SSETimeoutError } from './streamSSE';

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
      let mutResult: MutationResult | null = null;

      // Bounded by an AbortController + timeout via streamSSE, so a stream that
      // opens then hangs with zero bytes can't leave the mutation stuck inFlight.
      await streamSSE({
        open: (signal) => triggerMutation(sessionId, [targetId], guidance || undefined, signal),
        notOkMessage: (status) => `Mutation failed: ${status}`,
        onEvent: ({ event: eventType, data }) => {
          if (eventType === 'mutation_completed' && data.results) {
            const results = data.results as Array<Record<string, unknown>>;
            const r = results[0];
            if (r) {
              mutResult = {
                source_id: (r.source_id as string) ?? targetId,
                mutated_chord_symbols: (r.mutated_chord_symbols as string[]) ?? [],
                mutations: (r.mutations as MutationResult['mutations']) ?? [],
              };
            }
          }
        },
      });

      if (mutResult) setLastResult(mutResult);

      const res = await listCandidates(sessionId);
      setCandidates(res.items);
      return null;
    } catch (err) {
      if (err instanceof SSETimeoutError) return 'Mutation timed out after 10 minutes.';
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
