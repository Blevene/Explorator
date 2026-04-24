import { useEffect, useRef, useState } from 'react';

interface Props {
  isCurated: boolean | null;
  onToggle: (nextState: boolean) => void;
}

const DEBOUNCE_MS = 300;

export function StarButton({ isCurated, onToggle }: Props) {
  const disabled = isCurated === null;
  const label = isCurated ? 'Remove from curated' : 'Mark as curated';
  const filled = isCurated === true;
  const [busy, setBusy] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  const handleClick = () => {
    if (disabled || busy) return;
    setBusy(true);
    onToggle(!isCurated);
    // Trailing-edge debounce: ignore rapid second clicks while the first
    // request is in flight to avoid duplicate UserFeedbackEvent rows.
    timerRef.current = setTimeout(() => setBusy(false), DEBOUNCE_MS);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled}
      aria-label={label}
      aria-pressed={isCurated === true}
      title={disabled ? 'Available after the round completes' : label}
      className="p-1 rounded transition-opacity"
      style={{
        color: 'var(--accent-primary)',
        background: 'transparent',
        opacity: disabled ? 0.35 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
      }}
    >
      <svg
        width="16" height="16" viewBox="0 0 24 24"
        fill={filled ? 'currentColor' : 'none'}
        stroke={filled ? 'none' : 'currentColor'}
        strokeWidth="1.5"
        aria-hidden="true"
      >
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
      </svg>
    </button>
  );
}
