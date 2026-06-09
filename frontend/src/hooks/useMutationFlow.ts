import { useState, useRef, useEffect } from 'react';
import { triggerMutation, listCandidates } from '../services/api';
import { useCandidateStore } from '../stores/candidateStore';
import { streamSSE, SSETimeoutError, USER_ABORT } from './streamSSE';

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
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  const { candidates, setCandidates } = useCandidateStore();

  // Track mount status so post-await / `finally` setState calls can be gated:
  // a caller abort fired from the unmount cleanup still runs `finally`, which
  // would otherwise update state on an unmounted (dead) fiber.
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Abort any in-flight mutation on unmount / session change. Aborting closes
  // the client request; the backend cancels the in-flight round on disconnect
  // (best-effort), instead of leaking it until the timeout fires.
  useEffect(() => {
    return () => abortRef.current?.abort(USER_ABORT);
  }, [sessionId]);

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

    // Abort any prior in-flight controller before replacing it, so a re-entrant
    // call can't orphan a stream that's then only abortable by the timeout.
    abortRef.current?.abort(USER_ABORT);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      let mutResult: MutationResult | null = null;

      // Bounded by an AbortController + timeout via streamSSE, so a stream that
      // opens then hangs with zero bytes can't leave the mutation stuck inFlight.
      await streamSSE({
        signal: controller.signal,
        open: (signal) => triggerMutation(sessionId, [targetId], guidance || undefined, signal),
        notOkMessage: (status) => `Mutation failed: ${status}`,
        onEvent: ({ event: eventType, data }) => {
          // The mutate route can emit *_error over a 200 stream; without this a
          // failed mutation ends the stream normally and returns a false success.
          // Throw so it propagates → submit() returns the real error.
          if (eventType === 'mutation_error' || eventType === 'realization_error') {
            throw new Error((data.error as string) ?? 'Mutation failed');
          }
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

      if (mutResult && mountedRef.current) setLastResult(mutResult);

      const res = await listCandidates(sessionId);
      if (mountedRef.current) setCandidates(res.items);
      return null;
    } catch (err) {
      // A caller-driven abort (unmount / session change) isn't a failure to report.
      if (controller.signal.aborted && !(err instanceof SSETimeoutError)) {
        return 'Mutation cancelled';
      }
      if (err instanceof SSETimeoutError) return 'Mutation timed out after 10 minutes.';
      return err instanceof Error ? err.message : 'Mutation failed';
    } finally {
      // Ref reset is unconditional (not state). The state reset is gated on
      // mount: a caller abort fired from unmount cleanup still runs `finally`,
      // and updating state on a dead fiber is a no-op bug. Normal completion
      // runs with mountedRef.current === true, so inFlight still resets.
      if (abortRef.current === controller) abortRef.current = null;
      if (mountedRef.current) setInFlight(false);
    }
  };

  return {
    mutatingCandidateId, mutatingCandidate, inFlight,
    inFlightLabel, inFlightChords, lastResult,
    openModal, closeModal, submit, dismissResult,
  };
}
