export function EmptyState() {
  return (
    <div
      data-testid="empty-state"
      className="text-center py-12 text-sm"
      style={{ color: 'var(--text-muted)' }}
    >
      No patterns yet. Run a session and save its finalists to start your library.
    </div>
  );
}
