import { useEffect, useId, useMemo, useRef, useState } from 'react';

export interface PickerOption {
  value: string;
  label: string;
}

interface OptionPickerProps {
  value: string;
  onChange: (value: string) => void;
  options: PickerOption[];
  /** Accessible label + placeholder for the combobox. */
  ariaLabel: string;
  /** Prefix for data-testid hooks, e.g. `key-picker` / `mode-picker`. */
  testIdPrefix: string;
  disabled?: boolean;
  /** Visual hint; the input shrinks for the in-session re-generate bar. */
  compact?: boolean;
}

/**
 * Accessible type-ahead combobox over a fixed list of options. Generalised from
 * GenrePicker so Key / Mode (and future small fixed lists) share one a11y
 * implementation. Typing filters case-insensitively over label + value; the
 * selected option renders as its label and `onChange` emits the option value.
 */
export default function OptionPicker({
  value,
  onChange,
  options,
  ariaLabel,
  testIdPrefix,
  disabled = false,
  compact = false,
}: OptionPickerProps) {
  const listboxId = useId();
  const optionId = (v: string) => `${listboxId}-opt-${v}`;
  const [open, setOpen] = useState(false);
  // `query` is the raw text in the input. `null` means "show the selected
  // option's label"; a string means the user is actively typing a filter.
  const [query, setQuery] = useState<string | null>(null);
  const [highlight, setHighlight] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = useMemo(
    () => options.find((o) => o.value === value) ?? null,
    [options, value],
  );

  // When the selected `value` isn't in `options`, fall back to the raw value so
  // the input is never mysteriously blank.
  const displayValue = query ?? selected?.label ?? value ?? '';

  const filtered = useMemo(() => {
    const q = (query ?? '').trim().toLowerCase();
    if (!q) return options;
    return options.filter(
      (o) =>
        o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q),
    );
  }, [options, query]);

  // `highlight` can point past a shrunken `filtered` list after a re-filter.
  // Clamp to a valid index (>= 0) for styling, aria, and Enter selection.
  const safeHighlight = Math.min(highlight, filtered.length - 1);
  const activeOption = safeHighlight >= 0 ? filtered[safeHighlight] : undefined;

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery(null);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  const select = (o: PickerOption) => {
    onChange(o.value);
    setQuery(null);
    setOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setHighlight(() => Math.min(safeHighlight + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight(() => Math.max(safeHighlight - 1, 0));
    } else if (e.key === 'Enter') {
      if (open && activeOption) {
        e.preventDefault();
        select(activeOption);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
      setQuery(null);
      inputRef.current?.blur();
    }
  };

  return (
    <div ref={rootRef} className="relative" style={{ minWidth: compact ? '7rem' : '9rem' }}>
      <input
        ref={inputRef}
        type="text"
        role="combobox"
        data-testid={`${testIdPrefix}-input`}
        aria-expanded={open}
        aria-autocomplete="list"
        aria-controls={open ? listboxId : undefined}
        aria-activedescendant={open && activeOption ? optionId(activeOption.value) : undefined}
        aria-label={ariaLabel}
        placeholder={ariaLabel}
        disabled={disabled}
        value={displayValue}
        onChange={(e) => {
          const v = e.target.value;
          setQuery(v === '' ? null : v);
          setOpen(true);
          setHighlight(0);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        className={`w-full rounded-lg text-sm focus:outline-none disabled:opacity-40 transition-colors ${compact ? 'px-3 py-2' : 'px-4 py-2.5'}`}
        style={{
          background: 'var(--surface-1)',
          border: '1px solid var(--border-subtle)',
          color: 'var(--text-primary)',
        }}
      />
      {open && (
        <ul
          id={listboxId}
          role="listbox"
          aria-label={ariaLabel}
          className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-lg py-1 shadow-lg"
          style={{
            background: 'var(--surface-2)',
            border: '1px solid var(--border-default)',
          }}
        >
          {filtered.length === 0 ? (
            <li
              data-testid={`${testIdPrefix}-no-matches`}
              aria-disabled="true"
              className="px-4 py-2 text-sm"
              style={{ color: 'var(--text-muted)' }}
            >
              No matches
            </li>
          ) : (
            filtered.map((o, i) => {
              const isHighlighted = i === safeHighlight;
              const isSelected = o.value === value;
              return (
                <li
                  key={o.value}
                  id={optionId(o.value)}
                  role="option"
                  data-testid={`${testIdPrefix}-option-${o.value}`}
                  aria-selected={isSelected}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    select(o);
                  }}
                  onMouseEnter={() => setHighlight(i)}
                  className="cursor-pointer px-4 py-2 text-sm transition-colors"
                  style={{
                    background: isHighlighted ? 'var(--surface-3)' : 'transparent',
                    color: isSelected ? 'var(--accent-primary)' : 'var(--text-primary)',
                  }}
                >
                  {o.label}
                </li>
              );
            })
          )}
        </ul>
      )}
    </div>
  );
}
