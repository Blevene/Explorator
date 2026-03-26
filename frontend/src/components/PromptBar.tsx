interface PromptBarProps {
  prompt: string;
  onPromptChange: (value: string) => void;
  generationMode: string;
  onModeChange: (mode: string) => void;
  onGenerate: () => void;
  loading: boolean;
  currentNode: string | null;
}

const MODES = [
  { value: 'conservative', label: 'Conservative' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'exploratory', label: 'Exploratory' },
];

const PIPELINE_STEPS = [
  { key: 'parse_intent', label: 'Parsing intent' },
  { key: 'load_genre', label: 'Loading genre' },
  { key: 'generate', label: 'Generating' },
  { key: 'evaluate_progressions', label: 'Evaluating' },
  { key: 'select_top_progressions', label: 'Selecting' },
  { key: 'persist_round', label: 'Saving' },
];

export default function PromptBar({
  prompt,
  onPromptChange,
  generationMode,
  onModeChange,
  onGenerate,
  loading,
  currentNode,
}: PromptBarProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !loading) {
      onGenerate();
    }
  };

  // Find which step index matches the current node
  const stepIndex = currentNode
    ? PIPELINE_STEPS.findIndex((s) => s.key === currentNode)
    : -1;

  const pct = loading && stepIndex >= 0
    ? Math.round(((stepIndex + 1) / PIPELINE_STEPS.length) * 100)
    : loading ? 5 : 0;

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
          className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-purple-500 disabled:opacity-50"
        />
        <button
          onClick={onGenerate}
          disabled={loading || !prompt.trim()}
          className="bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-semibold px-5 py-2 rounded-lg transition-colors"
        >
          {loading ? 'Running...' : 'Generate'}
        </button>
      </div>

      {/* Mode toggle row */}
      <div className="flex items-center gap-2">
        <span className="text-gray-500 text-xs">Mode:</span>
        <div className="flex gap-1">
          {MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => onModeChange(m.value)}
              disabled={loading}
              className={`text-xs px-3 py-1 rounded transition-colors ${
                generationMode === m.value
                  ? 'bg-purple-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              } disabled:opacity-50`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Pipeline progress bar */}
      {loading && (
        <div className="flex flex-col gap-1.5 mt-1">
          {/* Bar */}
          <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-purple-500 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>
          {/* Step pills */}
          <div className="flex gap-1 flex-wrap">
            {PIPELINE_STEPS.map((step, i) => {
              const isDone = stepIndex > i;
              const isActive = stepIndex === i;
              return (
                <span
                  key={step.key}
                  className={`text-[10px] px-2 py-0.5 rounded transition-all duration-300 ${
                    isDone
                      ? 'bg-purple-900/50 text-purple-300'
                      : isActive
                        ? 'bg-purple-600 text-white'
                        : 'bg-gray-800 text-gray-600'
                  }`}
                >
                  {isDone ? '✓' : isActive ? '▸' : '○'} {step.label}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
