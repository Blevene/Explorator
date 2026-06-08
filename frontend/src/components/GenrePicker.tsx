import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { GenreSummary } from '../services/api';

interface GenrePickerProps {
  value: string;
  onChange: (genre: string) => void;
  genres: GenreSummary[];
  disabled?: boolean;
  /** Visual hint; the input shrinks for the in-session re-generate bar. */
  compact?: boolean;
}

/**
 * Accessible type-ahead combobox over the known genres.
 *
 * Typing filters case-insensitively over display_name + genre id. The selected
 * genre is rendered as its display_name; `onChange` always emits the genre id.
 */
export default function GenrePicker({
  value,
  onChange,
  genres,
  disabled = false,
  compact = false,
}: GenrePickerProps) {
  const listboxId = useId();
  const [open, setOpen] = useState(false);
  // `query` is the raw text in the input. `null` means "show the selected
  // genre's display_name"; a string means the user is actively typing a filter.
  const [query, setQuery] = useState<string | null>(null);
  const [highlight, setHighlight] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);

  const selected = useMemo(
    () => genres.find((g) => g.genre === value) ?? null,
    [genres, value],
  );

  const displayValue = query ?? selected?.display_name ?? '';

  const filtered = useMemo(() => {
    const q = (query ?? '').trim().toLowerCase();
    if (!q) return genres;
    return genres.filter(
      (g) =>
        g.display_name.toLowerCase().includes(q) ||
        g.genre.toLowerCase().includes(q),
    );
  }, [genres, query]);

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

  const select = (g: GenreSummary) => {
    onChange(g.genre);
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
      setHighlight((h) => Math.min(h + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === 'Enter') {
      if (open && filtered[highlight]) {
        e.preventDefault();
        select(filtered[highlight]);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
      setQuery(null);
    }
  };

  return (
    <div ref={rootRef} className="relative" style={{ minWidth: compact ? '9rem' : '11rem' }}>
      <input
        type="text"
        role="combobox"
        data-testid="genre-picker-input"
        aria-expanded={open}
        aria-autocomplete="list"
        aria-controls={listboxId}
        aria-label="Genre"
        placeholder="Genre"
        disabled={disabled}
        value={displayValue}
        onChange={(e) => {
          setQuery(e.target.value);
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
      {open && filtered.length > 0 && (
        <ul
          id={listboxId}
          role="listbox"
          aria-label="Genres"
          className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-lg py-1 shadow-lg"
          style={{
            background: 'var(--surface-2)',
            border: '1px solid var(--border-default)',
          }}
        >
          {filtered.map((g, i) => {
            const isHighlighted = i === highlight;
            const isSelected = g.genre === value;
            return (
              <li
                key={g.genre}
                role="option"
                data-testid={`genre-option-${g.genre}`}
                aria-selected={isSelected}
                onMouseDown={(e) => {
                  // Prevent the input blur from closing the list before select.
                  e.preventDefault();
                  select(g);
                }}
                onMouseEnter={() => setHighlight(i)}
                className="cursor-pointer px-4 py-2 text-sm transition-colors"
                style={{
                  background: isHighlighted ? 'var(--surface-3)' : 'transparent',
                  color: isSelected ? 'var(--accent-primary)' : 'var(--text-primary)',
                }}
              >
                {g.display_name}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
