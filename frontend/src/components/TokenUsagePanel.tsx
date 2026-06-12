import { useCandidateStore, sessionTokenTotals } from '../stores/candidateStore';

const fmt = (n: number) => n.toLocaleString('en-US');
const usd = (n: number) => `~$${n < 0.01 ? n.toFixed(4) : n.toFixed(3)} est.`;

export default function TokenUsagePanel() {
  const live = useCandidateStore((s) => s.live);
  const usages = useCandidateStore((s) => s.usages);
  const current = live ?? (usages.length ? usages[usages.length - 1] : null);
  const session = sessionTokenTotals(useCandidateStore.getState());

  if (!current) return null;

  const phases = Object.entries(current.by_phase).sort(
    (a, b) => b[1].input + b[1].output - (a[1].input + a[1].output),
  );

  return (
    <div
      data-testid="token-usage-panel"
      className="rounded-lg px-4 py-3 text-xs"
      style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
    >
      <div className="flex items-center justify-between">
        <span className="uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
          Token usage
        </span>
        <span className="font-mono" style={{ color: 'var(--text-primary)' }}>
          {fmt(current.total_tokens)} tokens
          <span style={{ color: 'var(--text-muted)' }}>
            {' '}({fmt(current.total_input)} in / {fmt(current.total_output)} out)
          </span>
          <span className="ml-2" style={{ color: 'var(--accent-primary)' }}>{usd(current.estimated_cost_usd)}</span>
        </span>
      </div>

      <details className="mt-2">
        <summary className="cursor-pointer" style={{ color: 'var(--text-muted)' }}>
          Breakdown by step
        </summary>
        <div className="mt-2 flex flex-col gap-1">
          {phases.map(([name, p]) => (
            <div key={name} className="flex items-center justify-between font-mono">
              <span style={{ color: 'var(--text-secondary)' }}>
                {name} <span style={{ color: 'var(--text-muted)' }}>({p.model})</span>
              </span>
              <span style={{ color: 'var(--text-muted)' }}>
                {fmt(p.input + p.output)} tokens · {p.calls} call{p.calls === 1 ? '' : 's'}
              </span>
            </div>
          ))}
        </div>
      </details>

      <div className="mt-2 pt-2 flex items-center justify-between" style={{ borderTop: '1px solid var(--border-subtle)' }}>
        <span style={{ color: 'var(--text-muted)' }}>This session</span>
        <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>
          {fmt(session.tokens)} tokens · {usd(session.cost)}
        </span>
      </div>
    </div>
  );
}
