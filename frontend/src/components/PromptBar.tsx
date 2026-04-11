interface PromptBarProps {
  prompt: string;
  onPromptChange: (value: string) => void;
  generationMode: string;
  onModeChange: (mode: string) => void;
  onGenerate: () => void;
  loading: boolean;
  currentNode: string | null;
  flowType?: 'generation' | 'realization';
}

const MODES = [
  { value: 'conservative', label: 'Conservative', desc: 'Fewer candidates, safer choices' },
  { value: 'balanced', label: 'Balanced', desc: 'Default — good variety' },
  { value: 'exploratory', label: 'Exploratory', desc: 'More candidates, bolder experiments' },
];

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
  generationMode,
  onModeChange,
  onGenerate,
  loading,
  currentNode,
  flowType = 'generation',
}: PromptBarProps) {
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
      {/* Input row */}
      <div className="flex gap-2">
        <input
          type="text"
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe the mood, genre, or style you want to explore..."
          disabled={loading}
          className="flex-1 px-4 py-2 rounded-lg text-sm focus:outline-none disabled:opacity-40 transition-colors"
          style={{
            background: 'var(--surface-1)',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-primary)',
          }}
        />
        <button
          onClick={onGenerate}
          disabled={loading || !prompt.trim()}
          className="px-5 py-2 rounded-lg font-medium text-sm transition-all disabled:opacity-30"
          style={{
            background: loading ? 'var(--surface-3)' : 'var(--accent-primary)',
            color: loading ? 'var(--text-muted)' : 'var(--surface-0)',
          }}
        >
          {loading ? 'Running...' : 'Generate'}
        </button>
      </div>

      {/* Mode toggle */}
      <div className="flex items-center gap-2">
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Mode</span>
        <div className="flex gap-1">
          {MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => onModeChange(m.value)}
              disabled={loading}
              title={m.desc}
              className="text-xs px-3 py-1 rounded transition-colors disabled:opacity-40"
              style={{
                background: generationMode === m.value ? 'var(--accent-primary-dim)' : 'var(--surface-3)',
                color: generationMode === m.value ? 'var(--accent-primary)' : 'var(--text-muted)',
                border: generationMode === m.value ? '1px solid var(--accent-primary)' : '1px solid transparent',
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Pipeline progress */}
      {loading && (
        <div className="flex flex-col gap-1.5 mt-1">
          <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--surface-3)' }}>
            <div
              className="h-full rounded-full transition-all duration-500 ease-out"
              style={{ width: `${pct}%`, background: 'var(--accent-primary)' }}
            />
          </div>
          <div className="flex gap-1 flex-wrap">
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
