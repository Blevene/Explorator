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
      <span className="w-20 truncate" style={{ color: 'var(--text-muted)' }} title={dimension}>{label}</span>
      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--surface-4)' }}>
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${barPct}%`, background: 'var(--accent-primary)' }}
        />
      </div>
      <span className="w-8 text-right font-mono" style={{ color: 'var(--text-secondary)' }}>{pct}%</span>
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
      <div className="rounded-lg px-3 py-2 text-sm" style={{ background: 'var(--surface-3)', color: 'var(--text-primary)' }}>
        {entry.content}
      </div>
      {summary && (
        <div
          className="rounded-lg px-3 py-2 text-xs"
          style={{ background: 'var(--accent-primary-dim)', border: '1px solid var(--accent-primary-dim)', color: 'var(--accent-primary)' }}
        >
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
    <div className="w-72 flex flex-col" style={{ borderLeft: '1px solid var(--border-subtle)', background: 'var(--surface-1)' }}>
      {/* Header */}
      <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>Feedback</h3>
      </div>

      {/* Weight visualization */}
      {currentWeights && (() => {
        const maxW = Math.max(...Object.values(currentWeights));
        return (
          <div className="px-4 py-3 space-y-1.5" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <h4 className="text-xs font-medium mb-2" style={{ color: 'var(--text-muted)' }}>Weights</h4>
            {Object.entries(currentWeights).map(([dim, weight]) => (
              <WeightBar key={dim} dimension={dim} weight={weight} maxWeight={maxW} />
            ))}
          </div>
        );
      })()}

      {/* Chat thread */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {entries.length === 0 && (
          <p className="text-xs text-center py-8" style={{ color: 'var(--text-muted)' }}>
            Type below to steer the search.
          </p>
        )}
        {entries.map((entry) => (
          <FeedbackMessage key={entry.id} entry={entry} />
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-2 text-xs" style={{ color: 'var(--score-low)', background: '#7f1d1d22' }}>
          {error}
        </div>
      )}

      {/* Input */}
      <div className="px-4 py-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit(); }}
            placeholder={candidateId ? '"more experimental"' : 'Select arrangement'}
            disabled={!candidateId || submitting}
            className="flex-1 rounded px-3 py-1.5 text-sm focus:outline-none disabled:opacity-40"
            style={{
              background: 'var(--surface-0)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)',
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || !candidateId || submitting}
            className="px-3 py-1.5 text-sm rounded font-medium disabled:opacity-30 transition-colors"
            style={{ background: 'var(--accent-primary)', color: 'var(--surface-0)' }}
          >
            {submitting ? '...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}
