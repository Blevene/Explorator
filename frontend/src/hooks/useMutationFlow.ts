import { useState } from 'react';
import { triggerMutation, listCandidates } from '../services/api';
import { useCandidateStore } from '../stores/candidateStore';

export function useMutationFlow(sessionId: string | undefined) {
  const [mutatingCandidateId, setMutatingCandidateId] = useState<string | null>(null);
  const [inFlight, setInFlight] = useState(false);

  const { candidates, setCandidates } = useCandidateStore();

  const openModal = (candidateId: string) => setMutatingCandidateId(candidateId);
  const closeModal = () => setMutatingCandidateId(null);

  const mutatingCandidate = candidates.find(c => c.candidate_id === mutatingCandidateId);

  const submit = async (guidance: string): Promise<string | null> => {
    if (!sessionId || !mutatingCandidateId) return 'No session or candidate';
    const targetId = mutatingCandidateId;
    setMutatingCandidateId(null);
    setInFlight(true);

    try {
      const response = await triggerMutation(sessionId, [targetId], guidance || undefined);
      if (!response.body) return 'No response body';
      const reader = response.body.getReader();
      while (true) {
        const { done } = await reader.read();
        if (done) break;
      }
      reader.releaseLock();

      const res = await listCandidates(sessionId);
      setCandidates(res.items);
      return null; // success
    } catch (err) {
      return err instanceof Error ? err.message : 'Mutation failed';
    } finally {
      setInFlight(false);
    }
  };

  return { mutatingCandidateId, mutatingCandidate, inFlight, openModal, closeModal, submit };
}
