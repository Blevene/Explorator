import { useState } from 'react';

interface MutateModalProps {
  candidateId: string;
  chordSymbols: string[];
  onSubmit: (guidance: string) => void;
  onClose: () => void;
}

export default function MutateModal({ chordSymbols, onSubmit, onClose }: MutateModalProps) {
  const [guidance, setGuidance] = useState('');

  return (
    <div className="fixed inset-0 flex items-center justify-center z-50" style={{ background: 'rgba(0,0,0,0.7)' }} onClick={onClose}>
      <div
        className="rounded-xl p-6 w-full max-w-md"
        style={{ background: 'var(--surface-2)', border: '1px solid var(--border-default)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Mutate Candidate</h3>

        <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>Current progression</div>
        <div
          className="font-mono text-sm rounded-lg p-3 mb-4"
          style={{ background: 'var(--surface-1)', color: 'var(--text-primary)' }}
        >
          {chordSymbols.join(' \u2192 ')}
        </div>

        <label className="block text-xs mb-1" style={{ color: 'var(--text-muted)' }}>
          Guidance (optional)
        </label>
        <input
          type="text"
          value={guidance}
          onChange={(e) => setGuidance(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSubmit(guidance)}
          placeholder="e.g., make it darker, more tension, add a deceptive cadence..."
          className="w-full rounded-lg px-3 py-2 text-sm mb-4 focus:outline-none"
          style={{
            background: 'var(--surface-1)',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-primary)',
          }}
          autoFocus
        />

        <div className="flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs rounded-lg transition-colors"
            style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}
          >
            Cancel
          </button>
          <button
            onClick={() => onSubmit(guidance)}
            className="px-4 py-1.5 text-xs rounded-lg font-medium transition-colors"
            style={{ background: 'var(--accent-secondary)', color: 'var(--surface-0)' }}
          >
            Mutate
          </button>
        </div>
      </div>
    </div>
  );
}
