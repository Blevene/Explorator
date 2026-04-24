interface Props {
  isCurated: boolean | null;
  onToggle: (nextState: boolean) => void;
}

export function StarButton({ isCurated, onToggle }: Props) {
  const disabled = isCurated === null;
  const label = isCurated ? 'Remove from curated' : 'Mark as curated';
  const filled = isCurated === true;

  const handleClick = () => {
    if (disabled) return;
    onToggle(!isCurated);
  };

  return (
    <button
      onClick={handleClick}
      aria-label={label}
      aria-pressed={isCurated === true}
      aria-disabled={disabled || undefined}
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
