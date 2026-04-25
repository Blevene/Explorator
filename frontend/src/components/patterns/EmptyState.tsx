import { Link } from 'react-router-dom';

export function EmptyState() {
  return (
    <div
      data-testid="empty-state"
      className="rounded-xl text-center px-6 py-16 flex flex-col items-center gap-3"
      style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
    >
      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
        Your pattern library is empty.
      </p>
      <p className="text-xs max-w-md" style={{ color: 'var(--text-muted)' }}>
        Patterns capture the harmonic, voicing, bass, and groove ideas you save as
        finalists. Start a session, explore, then star the candidates worth keeping.
      </p>
      <Link
        to="/"
        className="mt-2 px-4 py-1.5 rounded-lg text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-primary)]"
        style={{ background: 'var(--accent-primary)', color: 'var(--surface-0)' }}
      >
        Start a session →
      </Link>
    </div>
  );
}
