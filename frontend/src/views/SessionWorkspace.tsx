import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { listCandidates, getSession } from '../services/api';
import type { SessionSummary } from '../services/api';
import { useCandidateStore } from '../stores/candidateStore';
import { useArrangementStore } from '../stores/arrangementStore';
import { useGenerationFlow } from '../hooks/useGenerationFlow';
import { useRealizationFlow } from '../hooks/useRealizationFlow';
import { useMutationFlow } from '../hooks/useMutationFlow';
import CandidateCard from '../components/CandidateCard';
import PromptBar from '../components/PromptBar';
import ArrangementList from '../components/ArrangementList';
import ArrangementDetail from '../components/ArrangementDetail';
import LineageTree from '../components/LineageTree';
import MutateModal from '../components/MutateModal';
import FeedbackSidebar from '../components/FeedbackSidebar';
import { useFeedbackStore } from '../stores/feedbackStore';
import * as audioEngine from '../services/audioEngine';

export default function SessionWorkspace() {
  const { id } = useParams<{ id: string }>();
  const [session, setSession] = useState<SessionSummary | null>(null);
  const [prompt, setPrompt] = useState('');
  const [generationMode, setGenerationMode] = useState('balanced');
  const [viewMode, setViewMode] = useState<'generation' | 'realization'>('generation');

  const { candidates, setCandidates } = useCandidateStore();
  const arrangementStore = useArrangementStore();

  const generation = useGenerationFlow(id);
  const realization = useRealizationFlow(id);
  const mutation = useMutationFlow(id);

  const loading = generation.loading || realization.loading;
  const currentNode = generation.currentNode || realization.currentNode;

  useEffect(() => {
    if (!id) return;
    getSession(id)
      .then((s) => { setSession(s); if (s.prompt) setPrompt(s.prompt); })
      .catch(() => {});
    listCandidates(id)
      .then((res) => setCandidates(res.items))
      .catch(() => {});
  }, [id, setCandidates]);

  const handleGenerate = () => generation.generate(prompt, generationMode);

  const handleRealize = async (candidateId: string) => {
    const result = await realization.realize(candidateId);
    if (result === 'error') {
      generation.setError('Realization failed');
    } else {
      setViewMode('realization');
    }
  };

  const handleMutateSubmit = async (guidance: string) => {
    const err = await mutation.submit(guidance);
    if (err) generation.setError(err);
  };

  return (
    <div data-testid="session-workspace" className="max-w-6xl mx-auto p-8 flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/" data-testid="dashboard-link" className="text-xs font-medium transition-colors" style={{ color: 'var(--text-muted)' }}>
          &larr; Dashboard
        </Link>
        <div className="flex-1 min-w-0">
          <h1 data-testid="session-title" className="text-lg font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
            {session?.prompt || <span className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>{id}</span>}
          </h1>
          {session && (
            <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
              {session.mode} &middot; {session.status}{session.genre ? ` \u00b7 ${session.genre}` : ''}
            </p>
          )}
        </div>
      </div>

      {/* Prompt bar */}
      <div data-testid="prompt-section" className="rounded-lg p-4" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}>
        {currentNode?.startsWith('mutation_completed') && (() => {
          const parts = currentNode.split(':');
          return (
            <div className="text-xs font-mono mb-1" style={{ color: 'var(--accent-secondary)' }}>
              Round {parts[1]} — {parts[2]} mutation{parts[2] === '1' ? '' : 's'} applied, re-evaluating...
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

      {/* Error */}
      {generation.error && (
        <div data-testid="error-message" className="rounded-lg px-4 py-3 text-sm" style={{ background: '#7f1d1d33', border: '1px solid #7f1d1d', color: '#fca5a5' }}>
          {generation.error}
        </div>
      )}

      {viewMode === 'realization' ? (
        <>
          <button
            data-testid="back-to-progressions"
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
          <div className="flex flex-1 min-h-0 rounded-lg overflow-hidden" style={{ border: '1px solid var(--border-subtle)' }}>
            <ArrangementList
              arrangements={arrangementStore.arrangements}
              candidates={candidates}
              selectedId={arrangementStore.selectedArrangementId}
              onSelect={realization.selectArrangement}
              genre={session?.genre || 'dream_pop'}
              finalSelection={arrangementStore.finalSelection}
            />
            <ArrangementDetail
              arrangement={arrangementStore.selectedDetail}
              genre={session?.genre || 'dream_pop'}
            />
            {id && (
              <FeedbackSidebar
                sessionId={id}
                candidateId={arrangementStore.selectedArrangementId}
              />
            )}
          </div>
        </>
      ) : (
        <>
          {/* Mutation in-flight banner */}
          {mutation.inFlight && (
            <div data-testid="mutation-spinner" className="flex items-center gap-3 px-4 py-3 rounded-lg" style={{ background: 'var(--accent-secondary-dim)', border: '1px solid var(--accent-secondary)' }}>
              <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'var(--accent-secondary)', borderTopColor: 'transparent' }} />
              <span className="text-sm" style={{ color: 'var(--accent-secondary)' }}>Mutating candidate...</span>
            </div>
          )}

          {candidates.length > 0 ? (
            <div>
              <h2 data-testid="candidate-count" className="text-xs font-medium uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
                {candidates.length} candidate{candidates.length !== 1 ? 's' : ''}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {candidates.map((c, i) => (
                  <CandidateCard
                    key={c.candidate_id}
                    candidate={c}
                    index={i}
                    realized={realization.realizedCandidateIds.has(c.candidate_id)}
                    onRealize={handleRealize}
                    onMutate={mutation.openModal}
                    onClick={() => handleRealize(c.candidate_id)}
                  />
                ))}
              </div>
            </div>
          ) : (
            !loading && (
              <div data-testid="empty-state" className="rounded-lg p-8 text-center text-sm" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                No candidates yet. Enter a prompt above and click Generate to start exploring.
              </div>
            )
          )}

          <LineageTree
            candidates={candidates}
            onSelectCandidate={(cid) => handleRealize(cid)}
          />

          {loading && candidates.length === 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="rounded-lg p-4 h-48 animate-pulse" style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }} />
              ))}
            </div>
          )}
        </>
      )}

      {/* Mutation modal */}
      {mutation.mutatingCandidate && (
        <MutateModal
          candidateId={mutation.mutatingCandidate.candidate_id}
          chordSymbols={mutation.mutatingCandidate.chord_symbols}
          onSubmit={handleMutateSubmit}
          onClose={mutation.closeModal}
        />
      )}
    </div>
  );
}
