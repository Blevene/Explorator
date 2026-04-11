import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { listCandidates, getSession, listArrangements, getArrangement, triggerRealizationSSE, triggerMutation } from '../services/api';
import type { SessionSummary } from '../services/api';
import { useCandidateStore } from '../stores/candidateStore';
import { useArrangementStore } from '../stores/arrangementStore';
import CandidateCard from '../components/CandidateCard';
import PromptBar from '../components/PromptBar';
import ArrangementList from '../components/ArrangementList';
import ArrangementDetail from '../components/ArrangementDetail';
import LineageTree from '../components/LineageTree';
import MutateModal from '../components/MutateModal';
import FeedbackSidebar from '../components/FeedbackSidebar';
import { useFeedbackStore } from '../stores/feedbackStore';
import * as audioEngine from '../services/audioEngine';

const API_BASE = '/v1';

export default function SessionWorkspace() {
  const { id } = useParams<{ id: string }>();
  const [session, setSession] = useState<SessionSummary | null>(null);
  const [prompt, setPrompt] = useState('');
  const [generationMode, setGenerationMode] = useState('balanced');
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'generation' | 'realization'>('generation');
  const [mutatingCandidateId, setMutatingCandidateId] = useState<string | null>(null);
  const nodeRef = useRef<string | null>(null);

  const { candidates, setCandidates } = useCandidateStore();
  const arrangementStore = useArrangementStore();

  // Alias id → sessionId for readability in handlers
  const sessionId = id;

  useEffect(() => {
    if (!id) return;
    getSession(id)
      .then((s) => { setSession(s); if (s.prompt) setPrompt(s.prompt); })
      .catch(() => {});
    listCandidates(id)
      .then((res) => setCandidates(res.items))
      .catch(() => {});
  }, [id, setCandidates]);

  const handleGenerate = useCallback(async () => {
    if (!id || !prompt.trim() || loading) return;

    setLoading(true);
    setCurrentNode(null);
    nodeRef.current = null;
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/sessions/${id}/rounds`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt.trim(), generation_mode: generationMode }),
      });

      if (!response.ok) throw new Error(`Round failed: ${response.status}`);
      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      const TIMEOUT_MS = 600_000; // 10 minute max for multi-round pipelines

      try {
        const deadline = Date.now() + TIMEOUT_MS;

        while (true) {
          if (Date.now() > deadline) {
            setError('Round timed out after 10 minutes.');
            break;
          }

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
              arrangementStore.setFinalSelection(data.final_selection as any);
            }
          }

          // Yield to React render loop
          await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
        }
      } finally {
        reader.releaseLock();
      }

      // Reload candidates after stream ends
      try {
        const res = await listCandidates(id);
        setCandidates(res.items);
      } catch {
        setError('Failed to reload candidates after round.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger round.');
    } finally {
      setLoading(false);
      setCurrentNode(null);
    }
  }, [id, prompt, generationMode, loading, setCandidates]);

  const handleSelectArrangement = async (arrangementId: string) => {
    arrangementStore.setSelectedArrangementId(arrangementId);
    try {
      const detail = await getArrangement(arrangementId);
      arrangementStore.setSelectedDetail(detail);
    } catch (err: any) {
      setError(err.message || 'Failed to load arrangement');
    }
  };

  const handleRealize = async (candidateId: string) => {
    if (!sessionId) return;

    setError(null);

    // Check for existing arrangements first — skip realization if already done
    try {
      const existing = await listArrangements(candidateId);
      if (existing.length > 0) {
        arrangementStore.reset();
        arrangementStore.setArrangements(existing);
        setViewMode('realization');
        const best = existing.reduce((a, b) =>
          (a.weighted_total ?? 0) > (b.weighted_total ?? 0) ? a : b
        );
        await handleSelectArrangement(best.id);
        return;
      }
    } catch { /* no cached results, proceed with realization */ }

    // No existing arrangements — trigger realization
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
            if (eventType === 'node_started' && node) {
              setCurrentNode(node);
            } else if (eventType === 'realization_completed') {
              setCurrentNode(null);
            }
          } catch { /* skip */ }
        }
      }

      // Load arrangements
      const arrangements = await listArrangements(candidateId);
      arrangementStore.setArrangements(arrangements);
      setViewMode('realization');

      if (arrangements.length > 0) {
        const best = arrangements.reduce((a, b) =>
          (a.weighted_total ?? 0) > (b.weighted_total ?? 0) ? a : b
        );
        await handleSelectArrangement(best.id);
      }
    } catch (err: any) {
      setError(err.message || 'Realization failed');
    } finally {
      setLoading(false);
      setCurrentNode(null);
    }
  };

  const handleMutate = (candidateId: string) => {
    setMutatingCandidateId(candidateId);
  };

  const handleMutateSubmit = async (guidance: string) => {
    if (!sessionId || !mutatingCandidateId) return;
    setMutatingCandidateId(null);
    setError(null);

    try {
      const response = await triggerMutation(sessionId, [mutatingCandidateId], guidance || undefined);
      if (!response.body) return;
      const reader = response.body.getReader();
      while (true) {
        const { done } = await reader.read();
        if (done) break;
      }
      reader.releaseLock();

      // Reload candidates
      const res = await listCandidates(id!);
      setCandidates(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Mutation failed');
    }
  };

  const mutatingCandidate = candidates.find(c => c.candidate_id === mutatingCandidateId);

  return (
    <div className="max-w-6xl mx-auto p-8 flex flex-col gap-5">
      <div className="flex items-center gap-4">
        <Link to="/" className="text-xs font-medium transition-colors" style={{ color: 'var(--text-muted)' }}>
          &larr; Back
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
            {session?.prompt || <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>{id}</span>}
          </h1>
          {session && (
            <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
              {session.mode} &middot; {session.status}{session.genre ? ` &middot; ${session.genre}` : ''}
            </p>
          )}
        </div>
      </div>

      <div className="rounded-lg p-4" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
        {currentNode?.startsWith('mutation_completed') && (() => {
          const parts = currentNode.split(':');
          const round = parts[1];
          const mutations = parts[2];
          return (
            <div className="text-xs font-mono mb-1" style={{ color: 'var(--accent-secondary)' }}>
              Round {round} — {mutations} mutation{mutations === '1' ? '' : 's'} applied, re-evaluating...
            </div>
          );
        })()}
        <PromptBar
          prompt={prompt}
          onPromptChange={setPrompt}
          generationMode={generationMode}
          onModeChange={setGenerationMode}
          onGenerate={handleGenerate}
          loading={loading}
          currentNode={currentNode}
        />
      </div>

      {error && (
        <div className="rounded-lg px-4 py-3 text-sm" style={{ background: '#7f1d1d33', border: '1px solid #7f1d1d', color: '#fca5a5' }}>
          {error}
        </div>
      )}

      {viewMode === 'realization' ? (
        <>
          {/* Back button */}
          <button
            onClick={() => {
              setViewMode('generation');
              audioEngine.stop();
              arrangementStore.reset();
              useFeedbackStore.getState().reset();
            }}
            className="text-xs font-medium mb-2 transition-colors"
            style={{ color: 'var(--text-muted)' }}
          >
            &larr; Back to progressions
          </button>
          {/* Split panel */}
          <div className="flex flex-1 min-h-0 rounded-lg overflow-hidden border border-slate-700">
            <ArrangementList
              arrangements={arrangementStore.arrangements}
              candidates={candidates}
              selectedId={arrangementStore.selectedArrangementId}
              onSelect={handleSelectArrangement}
              genre={session?.genre || 'dream_pop'}
              finalSelection={arrangementStore.finalSelection}
            />
            <ArrangementDetail
              arrangement={arrangementStore.selectedDetail}
              genre={session?.genre || 'dream_pop'}
            />
            {sessionId && (
              <FeedbackSidebar
                sessionId={sessionId}
                candidateId={arrangementStore.selectedArrangementId}
              />
            )}
          </div>
        </>
      ) : (
        <>
          {candidates.length > 0 ? (
            <div>
              <h2 className="text-xs font-medium uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
                {candidates.length} candidate{candidates.length !== 1 ? 's' : ''}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {candidates.map((c, i) => (
                  <CandidateCard
                    key={c.candidate_id}
                    candidate={c}
                    index={i}
                    onRealize={handleRealize}
                    onMutate={handleMutate}
                    onClick={() => console.log('Selected:', c.candidate_id)}
                  />
                ))}
              </div>
            </div>
          ) : (
            !loading && (
              <div className="rounded-lg p-8 text-center text-sm" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                No candidates yet. Enter a prompt above and click Generate to start exploring.
              </div>
            )
          )}

          <LineageTree
            candidates={candidates}
            onSelectCandidate={(id) => {
              // Could scroll to or highlight the candidate
              console.log('Selected lineage node:', id);
            }}
          />

          {loading && candidates.length === 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="rounded-lg p-4 h-48 animate-pulse"
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Mutation modal */}
      {mutatingCandidate && (
        <MutateModal
          candidateId={mutatingCandidate.candidate_id}
          chordSymbols={mutatingCandidate.chord_symbols}
          onSubmit={handleMutateSubmit}
          onClose={() => setMutatingCandidateId(null)}
        />
      )}
    </div>
  );
}
