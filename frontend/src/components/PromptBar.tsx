interface PromptBarProps {
  prompt: string;
  onPromptChange: (value: string) => void;
  generationMode: string;
  onModeChange: (mode: string) => void;
  onGenerate: () => void;
  loading: boolean;
  progress: string | null;
}

const MODES = [
  { value: 'conservative', label: 'Conservative' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'exploratory', label: 'Exploratory' },
];

export default function PromptBar({
  prompt,
  onPromptChange,
  generationMode,
  onModeChange,
  onGenerate,
  loading,
  progress,
}: PromptBarProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !loading) {
      onGenerate();
    }
  };

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
          {loading ? 'Running…' : 'Generate'}
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

      {/* Progress indicator */}
      {loading && progress && (
        <p className="text-xs text-purple-400 animate-pulse">{progress}</p>
      )}
    </div>
  );
}
