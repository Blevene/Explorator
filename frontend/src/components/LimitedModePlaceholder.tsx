interface Props {
  feature: string;
}

/**
 * Rendered in place of a database-backed view when the backend is running in
 * limited (in-memory) mode. The route is kept registered so a bookmarked URL
 * doesn't 404 in-app — it just shows why the feature is unavailable.
 */
export default function LimitedModePlaceholder({ feature }: Props) {
  return (
    <div className="px-8 py-12">
      <div className="max-w-2xl mx-auto">
        <div
          data-testid="limited-mode-placeholder"
          className="rounded-xl p-8 text-center"
          style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
        >
          <h1 className="text-xl font-light mb-2" style={{ color: 'var(--text-primary)' }}>
            {feature} unavailable in limited mode
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Long-term memory is off because the database is not connected. Start Neo4j to
            enable durable storage and learning features. Generation still works normally.
          </p>
        </div>
      </div>
    </div>
  );
}
