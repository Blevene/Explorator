/**
 * Degradation indicator shown when the backend runs without a durable graph
 * backend ("memory" persistence). Rendered by AppShell and the Dashboard
 * (which lives outside AppShell) so the banner appears on every surface.
 */
export default function LimitedModeBanner() {
  return (
    <div
      role="status"
      data-testid="limited-mode-banner"
      className="px-6 py-2 text-xs text-center"
      style={{
        background: 'var(--score-mid-faint)',
        borderBottom: '1px solid var(--score-mid)',
        color: 'var(--score-mid)',
      }}
    >
      <span style={{ color: 'var(--text-secondary)' }}>
        <strong style={{ color: 'var(--score-mid)' }}>Limited mode</strong>
        {' — long-term memory is off (pattern library, history, lineage, and learning are '}
        disabled). Generation works normally.
      </span>
    </div>
  );
}
