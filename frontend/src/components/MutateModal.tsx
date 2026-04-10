import { useState } from 'react';

interface MutateModalProps {
  candidateId: string;
  chordSymbols: string[];
  onSubmit: (guidance: string) => void;
  onClose: () => void;
}

export default function MutateModal({ candidateId, chordSymbols, onSubmit, onClose }: MutateModalProps) {
  const [guidance, setGuidance] = useState('');

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-gray-900 border border-gray-700 rounded-lg p-6 w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-white font-semibold mb-3">Mutate Candidate</h3>

        <div className="text-xs text-gray-400 mb-1">Current progression:</div>
        <div className="font-mono text-sm text-white bg-gray-800 rounded p-2 mb-4">
          {chordSymbols.join(' → ')}
        </div>

        <label className="block text-xs text-gray-400 mb-1">
          Guidance (optional)
        </label>
        <input
          type="text"
          value={guidance}
          onChange={(e) => setGuidance(e.target.value)}
          placeholder="e.g., make it darker, more tension..."
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-purple-500 mb-4"
        />

        <div className="flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs rounded bg-gray-800 text-gray-400 hover:bg-gray-700"
          >
            Cancel
          </button>
          <button
            onClick={() => onSubmit(guidance)}
            className="px-4 py-1.5 text-xs rounded bg-purple-600 text-white hover:bg-purple-500"
          >
            Mutate
          </button>
        </div>
      </div>
    </div>
  );
}
