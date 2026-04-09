import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { listCandidates, getSession, listArrangements, getArrangement, triggerRealizationSSE } from '../services/api';
import type { SessionSummary } from '../services/api';
import { useCandidateStore } from '../stores/candidateStore';
import { useArrangementStore } from '../stores/arrangementStore';
import CandidateCard from '../components/CandidateCard';
import PromptBar from '../components/PromptBar';
import ArrangementList from '../components/ArrangementList';
import ArrangementDetail from '../components/ArrangementDetail';
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
      const TIMEOUT_MS = 120_000; // 2 minute max round time

      try {
        const deadline = Date.now() + TIMEOUT_MS;

        while (true) {
          if (Date.now() > deadline) {
            setError('Round timed out after 2 minutes.');
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

    setCurrentNode('load_context');
    setLoading(true);
    setError(null);

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
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.slice(5).trim());
              if (data.node) setCurrentNode(data.node);
            } catch { /* skip */ }
          }
        }
      }

      // Load arrangements
      const arrangements = await listArrangements(candidateId);
      arrangementStore.setArrangements(arrangements);
      setViewMode('realization');

      // Auto-select best
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

  return (
    <div className="max-w-6xl mx-auto p-8 flex flex-col gap-6">
      <div>
        <Link to="/" className="text-purple-400 hover:text-purple-300 text-sm mb-2 inline-block">
          &larr; Back to Dashboard
        </Link>
        <h1 className="text-2xl font-bold">
          {session?.prompt ? (
            <span className="text-white">{session.prompt}</span>
          ) : (
            <span className="text-gray-400 font-mono text-base">{id}</span>
          )}
        </h1>
        {session && (
          <p className="text-gray-500 text-xs mt-1">
            {session.mode} &middot; {session.status}
          </p>
        )}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
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
        <div className="bg-red-900/40 border border-red-700 rounded-lg px-4 py-3 text-red-300 text-sm">
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
            }}
            className="text-xs text-slate-500 hover:text-slate-300 mb-2"
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
            />
            <ArrangementDetail
              arrangement={arrangementStore.selectedDetail}
              genre={session?.genre || 'dream_pop'}
            />
          </div>
        </>
      ) : (
        <>
          {candidates.length > 0 ? (
            <div>
              <h2 className="text-sm font-semibold text-gray-400 mb-3">
                {candidates.length} candidate{candidates.length !== 1 ? 's' : ''}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {candidates.map((c, i) => (
                  <CandidateCard
                    key={c.candidate_id}
                    candidate={c}
                    index={i}
                    onRealize={handleRealize}
                    onClick={() => console.log('Selected:', c.candidate_id)}
                  />
                ))}
              </div>
            </div>
          ) : (
            !loading && (
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center text-gray-500 text-sm">
                No candidates yet. Enter a prompt above and click Generate to start exploring.
              </div>
            )
          )}

          {loading && candidates.length === 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="bg-gray-900 border border-gray-800 rounded-lg p-4 h-48 animate-pulse"
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
