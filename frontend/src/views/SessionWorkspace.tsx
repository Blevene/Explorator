import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { listCandidates, triggerRoundSSE, getSession } from '../services/api';
import type { SessionSummary } from '../services/api';
import { readSSEStream } from '../services/sse';
import { useCandidateStore } from '../stores/candidateStore';
import CandidateCard from '../components/CandidateCard';
import PromptBar from '../components/PromptBar';

export default function SessionWorkspace() {
  const { id } = useParams<{ id: string }>();
  const [session, setSession] = useState<SessionSummary | null>(null);
  const [prompt, setPrompt] = useState('');
  const [generationMode, setGenerationMode] = useState('balanced');
  const [currentNode, setCurrentNode] = useState<string | null>(null);

  const { candidates, loading, error, setCandidates, setLoading, setError } =
    useCandidateStore();

  // Load session info and existing candidates on mount
  useEffect(() => {
    if (!id) return;

    getSession(id)
      .then((s) => {
        setSession(s);
        if (s.prompt) setPrompt(s.prompt);
      })
      .catch(() => {});

    listCandidates(id)
      .then((res) => setCandidates(res.items))
      .catch(() => {});
  }, [id, setCandidates]);

  const handleGenerate = async () => {
    if (!id || !prompt.trim() || loading) return;

    setLoading(true);
    setCurrentNode(null);
    setError(null);

    try {
      const response = await triggerRoundSSE(id, prompt.trim(), generationMode);

      await readSSEStream(
        response,
        (event) => {
          const node = (event.data.node as string) ?? null;
          switch (event.type) {
            case 'node_started':
              if (node) setCurrentNode(node);
              break;
            case 'node_completed':
              // Keep showing the completed node until next starts
              break;
            case 'candidates_preview':
              setCurrentNode('generate');
              break;
            case 'round_completed':
              setCurrentNode('persist_round');
              break;
            case 'round_error':
              setError((event.data.error as string) ?? 'An error occurred.');
              setLoading(false);
              setCurrentNode(null);
              break;
          }
        },
        async () => {
          // Stream finished — reload candidates
          try {
            const res = await listCandidates(id);
            setCandidates(res.items);
          } catch {
            // Ignore reload errors
          }
          setLoading(false);
          setCurrentNode(null);
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger round.');
      setLoading(false);
      setCurrentNode(null);
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-8 flex flex-col gap-6">
      {/* Back link + session header */}
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

      {/* Prompt bar */}
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

      {/* Error banner */}
      {error && (
        <div className="bg-red-900/40 border border-red-700 rounded-lg px-4 py-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Candidate grid */}
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

      {/* Loading skeleton placeholder */}
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
    </div>
  );
}
