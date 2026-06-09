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
  const optionId = (genre: string) => `${listboxId}-opt-${genre}`;
  const [open, setOpen] = useState(false);
  // `query` is the raw text in the input. `null` means "show the selected
  // genre's display_name"; a string means the user is actively typing a filter.
  // An empty string is normalised to `null` (revert to selected) on change.
  const [query, setQuery] = useState<string | null>(null);
  const [highlight, setHighlight] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = useMemo(
    () => genres.find((g) => g.genre === value) ?? null,
    [genres, value],
  );

  // When the selected `value` isn't in `genres` (stale/loading), fall back to
  // displaying the raw id so the input is never mysteriously blank.
  const displayValue = query ?? selected?.display_name ?? value ?? '';

  const filtered = useMemo(() => {
    const q = (query ?? '').trim().toLowerCase();
    if (!q) return genres;
    return genres.filter(
      (g) =>
        g.display_name.toLowerCase().includes(q) ||
        g.genre.toLowerCase().includes(q),
    );
  }, [genres, query]);

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
    <div ref={rootRef} className="relative" style={{ minWidth: compact ? '9rem' : '11rem' }}>
      <input
        ref={inputRef}
        type="text"
        role="combobox"
        data-testid="genre-picker-input"
        // Stay honest: only claim expanded when an actual listbox is rendered.
        aria-expanded={open}
        aria-autocomplete="list"
        // Only reference the listbox while it's actually rendered (open), so the
        // control never points at a non-existent element.
        aria-controls={open ? listboxId : undefined}
        aria-activedescendant={open && activeOption ? optionId(activeOption.genre) : undefined}
        aria-label="Genre"
        placeholder="Genre"
        disabled={disabled}
        value={displayValue}
        onChange={(e) => {
          const v = e.target.value;
          // Empty input reverts to showing the selected genre, not a blank.
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
          aria-label="Genres"
          className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-lg py-1 shadow-lg"
          style={{
            background: 'var(--surface-2)',
            border: '1px solid var(--border-default)',
          }}
        >
          {filtered.length === 0 ? (
            <li
              data-testid="genre-no-matches"
              aria-disabled="true"
              className="px-4 py-2 text-sm"
              style={{ color: 'var(--text-muted)' }}
            >
              No matches
            </li>
          ) : (
            filtered.map((g, i) => {
              const isHighlighted = i === safeHighlight;
              const isSelected = g.genre === value;
              return (
                <li
                  key={g.genre}
                  id={optionId(g.genre)}
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
            })
          )}
        </ul>
      )}
    </div>
  );
}
