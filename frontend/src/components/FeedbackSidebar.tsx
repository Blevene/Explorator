import { useState, useRef, useEffect } from 'react';
import { useFeedbackStore } from '../stores/feedbackStore';
import { submitFeedback } from '../services/api';
import type { FeedbackEntry } from '../stores/feedbackStore';

interface FeedbackSidebarProps {
  sessionId: string;
  candidateId: string | null;
}

const DIMENSION_LABELS: Record<string, string> = {
  genre_fit: 'Genre Fit',
  emotional_fit: 'Emotional',
  theoretical_coherence: 'Theory',
  cadence_quality: 'Cadence',
  novelty: 'Novelty',
  loopability: 'Loopability',
  voice_leading: 'Voice Lead.',
  register_density: 'Register',
  playability: 'Playability',
};

function WeightBar({ dimension, weight, maxWeight }: { dimension: string; weight: number; maxWeight: number }) {
  const pct = Math.round(weight * 100);
  const barPct = maxWeight > 0 ? Math.round((weight / maxWeight) * 100) : 0;
  const label = DIMENSION_LABELS[dimension] || dimension;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-gray-500 truncate" title={dimension}>{label}</span>
      <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-purple-500 rounded-full transition-all duration-300"
          style={{ width: `${barPct}%` }}
        />
      </div>
      <span className="w-10 text-right text-gray-400">{pct}%</span>
    </div>
  );
}

function FeedbackMessage({ entry }: { entry: FeedbackEntry }) {
  const adjustments = entry.interpreted_adjustments;
  const summary = Object.entries(adjustments)
    .filter(([k]) => k !== 'satisfaction')
    .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
    .join(', ');

  return (
    <div className="space-y-1">
      <div className="bg-gray-800 rounded-lg px-3 py-2 text-sm text-gray-200">
        {entry.content}
      </div>
      {summary && (
        <div className="bg-purple-900/30 border border-purple-800/50 rounded-lg px-3 py-2 text-xs text-purple-300">
          Understood: {summary}
        </div>
      )}
    </div>
  );
}

export default function FeedbackSidebar({ sessionId, candidateId }: FeedbackSidebarProps) {
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const { entries, currentWeights, submitting, error, addEntry, setSubmitting, setError } = useFeedbackStore();

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [entries.length]);

  const handleSubmit = async () => {
    if (!input.trim() || !candidateId || submitting) return;
    const text = input.trim();
    setInput('');
    setSubmitting(true);
    setError(null);

    try {
      const response = await submitFeedback(sessionId, candidateId, text);
      addEntry({
        id: response.id,
        content: text,
        interpreted_adjustments: response.interpreted_adjustments,
        adjusted_weights: response.adjusted_weights,
        satisfaction: response.satisfaction,
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit feedback');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="w-80 border-l border-gray-800 bg-gray-950 flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800">
        <h3 className="text-sm font-semibold text-gray-300">Feedback</h3>
        <p className="text-xs text-gray-600 mt-0.5">Tell me what to change</p>
      </div>

      {/* Weight visualization */}
      {currentWeights && (() => {
        const maxW = Math.max(...Object.values(currentWeights));
        return (
          <div className="px-4 py-3 border-b border-gray-800 space-y-1.5">
            <h4 className="text-xs font-medium text-gray-500 mb-2">Current Weights</h4>
            {Object.entries(currentWeights).map(([dim, weight]) => (
              <WeightBar key={dim} dimension={dim} weight={weight} maxWeight={maxW} />
            ))}
          </div>
        );
      })()}

      {/* Chat thread */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {entries.length === 0 && (
          <p className="text-xs text-gray-600 text-center py-8">
            No feedback yet. Type below to steer the search.
          </p>
        )}
        {entries.map((entry) => (
          <FeedbackMessage key={entry.id} entry={entry} />
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-2 text-xs text-red-400 bg-red-900/20">
          {error}
        </div>
      )}

      {/* Input */}
      <div className="px-4 py-3 border-t border-gray-800">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit(); }}
            placeholder={candidateId ? 'e.g. "more experimental"' : 'Select a candidate first'}
            disabled={!candidateId || submitting}
            className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-white placeholder-gray-600 focus:border-purple-500 focus:outline-none disabled:opacity-50"
          />
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || !candidateId || submitting}
            className="px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-500 text-white rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? '...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}
