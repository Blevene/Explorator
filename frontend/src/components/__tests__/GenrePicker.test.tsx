import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import GenrePicker from '../GenrePicker';

const GENRES = [
  { genre: 'dream_pop', display_name: 'Dream Pop' },
  { genre: 'shoegaze', display_name: 'Shoegaze' },
  { genre: 'synthwave', display_name: 'Synthwave' },
];

function setup(value = '', onChange = vi.fn()) {
  render(<GenrePicker value={value} onChange={onChange} genres={GENRES} />);
  return { onChange, input: screen.getByTestId('genre-picker-input') };
}

describe('GenrePicker', () => {
  it('opens the listbox on focus and renders all options', () => {
    const { input } = setup();
    fireEvent.focus(input);
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    expect(screen.getByTestId('genre-option-dream_pop')).toHaveTextContent('Dream Pop');
    expect(screen.getByTestId('genre-option-shoegaze')).toBeInTheDocument();
    expect(screen.getByTestId('genre-option-synthwave')).toBeInTheDocument();
  });

  it('filters options case-insensitively over display_name and genre id', () => {
    const { input } = setup();
    fireEvent.change(input, { target: { value: 'shoe' } });
    expect(screen.getByTestId('genre-option-shoegaze')).toBeInTheDocument();
    expect(screen.queryByTestId('genre-option-dream_pop')).not.toBeInTheDocument();

    // genre id match (underscore form)
    fireEvent.change(input, { target: { value: 'dream_p' } });
    expect(screen.getByTestId('genre-option-dream_pop')).toBeInTheDocument();
    expect(screen.queryByTestId('genre-option-shoegaze')).not.toBeInTheDocument();
  });

  it('calls onChange with the genre id when an option is clicked', () => {
    const { input, onChange } = setup();
    fireEvent.focus(input);
    fireEvent.mouseDown(screen.getByTestId('genre-option-synthwave'));
    expect(onChange).toHaveBeenCalledWith('synthwave');
  });

  it('selects the highlighted option via keyboard (ArrowDown + Enter)', () => {
    const { input, onChange } = setup();
    fireEvent.focus(input);
    // highlight starts at 0 (dream_pop); ArrowDown -> shoegaze
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith('shoegaze');
  });

  it('closes the list on Escape', () => {
    const { input } = setup();
    fireEvent.focus(input);
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('shows the selected genre display_name in the input', () => {
    const { input } = setup('dream_pop');
    expect(input).toHaveValue('Dream Pop');
  });

  it('exposes combobox a11y attributes', () => {
    const { input } = setup();
    expect(input).toHaveAttribute('role', 'combobox');
    expect(input).toHaveAttribute('aria-autocomplete', 'list');
    expect(input).toHaveAttribute('aria-expanded', 'false');
    fireEvent.focus(input);
    expect(input).toHaveAttribute('aria-expanded', 'true');
  });

  it('points aria-activedescendant at the highlighted option', () => {
    const { input } = setup();
    fireEvent.focus(input);
    // highlight starts at 0 (dream_pop)
    const first = screen.getByTestId('genre-option-dream_pop');
    expect(input.getAttribute('aria-activedescendant')).toBe(first.id);
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    const second = screen.getByTestId('genre-option-shoegaze');
    expect(input.getAttribute('aria-activedescendant')).toBe(second.id);
  });

  it('does not select a stale highlight after the filtered list shrinks', () => {
    const { input, onChange } = setup();
    fireEvent.focus(input);
    // Move highlight to index 2 (synthwave), then filter down to a 1-item list.
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.change(input, { target: { value: 'shoe' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    // Enter selects the clamped highlight (the only remaining match), never undefined.
    expect(onChange).toHaveBeenCalledWith('shoegaze');
  });

  it('reverts to the selected display_name when the field is cleared', () => {
    const { input } = setup('dream_pop');
    expect(input).toHaveValue('Dream Pop');
    fireEvent.change(input, { target: { value: 'shoe' } });
    expect(input).toHaveValue('shoe');
    fireEvent.change(input, { target: { value: '' } });
    // Empty input reverts to the selected genre rather than going blank.
    expect(input).toHaveValue('Dream Pop');
  });

  it('renders a non-selectable "No matches" row when nothing matches', () => {
    const { input, onChange } = setup();
    fireEvent.change(input, { target: { value: 'zzzzz' } });
    expect(screen.queryByRole('option')).toBeNull();
    const noMatches = screen.getByTestId('genre-no-matches');
    expect(noMatches).toHaveTextContent('No matches');
    // The listbox is still present, so aria-expanded stays honest.
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('falls back to the raw value when it is not a known genre', () => {
    const { input } = setup('unknown_genre');
    expect(input).toHaveValue('unknown_genre');
  });

  it('closes and blurs the input on Escape', () => {
    const { input } = setup();
    fireEvent.focus(input);
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(input).not.toHaveFocus();
  });
});
