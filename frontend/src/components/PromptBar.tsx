import GenrePicker from './GenrePicker';
import KeyPicker from './KeyPicker';
import ModePicker from './ModePicker';
import type { GenreSummary } from '../services/api';

interface PromptBarProps {
  prompt: string;
  onPromptChange: (value: string) => void;
  onGenerate: () => void;
  loading: boolean;
  currentNode: string | null;
  flowType?: 'generation' | 'realization';
  /** Genre / key / mode pickers are only shown for the generation flow. */
  genre?: string;
  onGenreChange?: (genre: string) => void;
  genres?: GenreSummary[];
  musicalKey?: string;
  onKeyChange?: (key: string) => void;
  musicalMode?: string;
  onMusicalModeChange?: (musicalMode: string) => void;
}

const GENERATION_STEPS = [
  { key: 'parse_intent', label: 'Intent' },
  { key: 'load_genre', label: 'Genre' },
  { key: 'load_memory', label: 'Memory' },
  { key: 'generate', label: 'Generate' },
  { key: 'evaluate_progressions', label: 'Evaluate' },
  { key: 'select_top_progressions', label: 'Select' },
  { key: 'load_context', label: 'Context' },
  { key: 'plan_voicings', label: 'Voicings' },
  { key: 'generate_bass', label: 'Bass' },
  { key: 'assemble', label: 'Assemble' },
  { key: 'evaluate_arrangements', label: 'Eval Arr.' },
  { key: 'rank_and_select', label: 'Rank' },
  { key: 'check_stop', label: 'Check' },
  { key: 'persist_realization', label: 'Save' },
  { key: 'persist_round', label: 'Done' },
];

const REALIZATION_STEPS = [
  { key: 'load_context', label: 'Context' },
  { key: 'plan_voicings', label: 'Voicings' },
  { key: 'generate_bass', label: 'Bass' },
  { key: 'assemble', label: 'Assemble' },
  { key: 'evaluate_arrangements', label: 'Eval Arr.' },
  { key: 'rank_and_select', label: 'Rank' },
  { key: 'persist_realization', label: 'Save' },
];

export default function PromptBar({
  prompt,
  onPromptChange,
  onGenerate,
  loading,
  currentNode,
  flowType = 'generation',
  genre = '',
  onGenreChange,
  genres = [],
  musicalKey = 'C',
  onKeyChange,
  musicalMode = 'major',
  onMusicalModeChange,
}: PromptBarProps) {
  const showGenrePicker = flowType === 'generation' && !!onGenreChange;
  const showKeyPicker = flowType === 'generation' && !!onKeyChange;
  const showModePicker = flowType === 'generation' && !!onMusicalModeChange;
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !loading) onGenerate();
  };

  const steps = flowType === 'realization' ? REALIZATION_STEPS : GENERATION_STEPS;

  const stepIndex = currentNode
    ? steps.findIndex((s) => s.key === currentNode)
    : -1;

  const pct = loading && stepIndex >= 0
    ? Math.round(((stepIndex + 1) / steps.length) * 100)
    : loading ? 3 : 0;

  return (
    <div className="flex flex-col gap-2">
      {/* Genre / key / mode pickers — equal columns on their own row so the mood
          box keeps full width and nothing gets cut off when all three show. */}
      {(showGenrePicker || showKeyPicker || showModePicker) && (
        <div className="grid grid-cols-3 gap-2">
          {showGenrePicker && (
            <GenrePicker
              value={genre}
              onChange={onGenreChange!}
              genres={genres}
              disabled={loading}
              compact
            />
          )}
          {showKeyPicker && (
            <KeyPicker value={musicalKey} onChange={onKeyChange!} disabled={loading} compact />
          )}
          {showModePicker && (
            <ModePicker value={musicalMode} onChange={onMusicalModeChange!} disabled={loading} compact />
          )}
        </div>
      )}

      {/* Mood / feeling input + generate */}
      <div className="flex gap-2">
        <input
          type="text"
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Mood, feeling, customization (optional)…"
          aria-label="Generation prompt"
          disabled={loading}
          className="flex-1 min-w-0 px-4 py-2 rounded-lg text-sm focus:outline-none disabled:opacity-40 transition-colors"
          style={{
            background: 'var(--surface-1)',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-primary)',
          }}
        />
        <button
          onClick={onGenerate}
          disabled={loading || (!prompt.trim() && !(showGenrePicker && genre))}
          className="px-5 py-2 rounded-lg font-medium text-sm transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          style={{
            background: loading ? 'var(--surface-3)' : 'var(--accent-primary)',
            color: loading ? 'var(--text-muted)' : 'var(--surface-0)',
          }}
        >
          {loading ? 'Running...' : 'Generate'}
        </button>
      </div>

      {/* Pipeline progress */}
      {loading && (
        <div
          role="status"
          aria-live="polite"
          aria-label={
            stepIndex >= 0
              ? `Pipeline progress: ${steps[stepIndex]?.label ?? 'starting'}, step ${stepIndex + 1} of ${steps.length}`
              : 'Pipeline starting'
          }
          className="flex flex-col gap-1.5 mt-1"
        >
          <div
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-1 rounded-full overflow-hidden"
            style={{ background: 'var(--surface-3)' }}
          >
            <div
              className="h-full rounded-full transition-all duration-500 ease-out"
              style={{ width: `${pct}%`, background: 'var(--accent-primary)' }}
            />
          </div>
          <div className="flex gap-1 flex-wrap" aria-hidden="true">
            {steps.map((step, i) => {
              const isDone = stepIndex > i;
              const isActive = stepIndex === i;
              return (
                <span
                  key={step.key}
                  className="font-mono transition-all duration-300"
                  style={{
                    fontSize: '9px',
                    padding: '1px 6px',
                    borderRadius: '3px',
                    background: isDone
                      ? 'var(--accent-primary-dim)'
                      : isActive
                        ? 'var(--accent-primary)'
                        : 'var(--surface-3)',
                    color: isDone
                      ? 'var(--accent-primary)'
                      : isActive
                        ? 'var(--surface-0)'
                        : 'var(--text-muted)',
                  }}
                >
                  {step.label}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
