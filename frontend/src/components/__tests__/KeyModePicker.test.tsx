import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import KeyPicker from '../KeyPicker';
import ModePicker from '../ModePicker';
import { KEY_OPTIONS, DEFAULT_KEY, MODE_OPTIONS, DEFAULT_MODE } from '../musicOptions';

describe('KeyPicker', () => {
  it('exposes the contracted key spellings as options', () => {
    expect(KEY_OPTIONS.map((o) => o.value)).toEqual([
      'C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B',
    ]);
    expect(DEFAULT_KEY).toBe('C');
  });

  it('opens the listbox on focus and renders all key options', () => {
    render(<KeyPicker value="C" onChange={vi.fn()} />);
    const input = screen.getByTestId('key-picker-input');
    fireEvent.focus(input);
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    for (const o of KEY_OPTIONS) {
      expect(screen.getByTestId(`key-picker-option-${o.value}`)).toHaveTextContent(o.label);
    }
  });

  it('calls onChange with the key value when an option is clicked', () => {
    const onChange = vi.fn();
    render(<KeyPicker value="C" onChange={onChange} />);
    const input = screen.getByTestId('key-picker-input');
    fireEvent.focus(input);
    fireEvent.mouseDown(screen.getByTestId('key-picker-option-Eb'));
    expect(onChange).toHaveBeenCalledWith('Eb');
  });

  it('shows the selected key in the input and exposes combobox a11y', () => {
    render(<KeyPicker value="F#" onChange={vi.fn()} />);
    const input = screen.getByTestId('key-picker-input');
    expect(input).toHaveValue('F#');
    expect(input).toHaveAttribute('role', 'combobox');
    expect(input).toHaveAttribute('aria-label', 'Key');
  });
});

describe('ModePicker', () => {
  it('exposes the contracted modes (lowercase value, capitalized label)', () => {
    expect(MODE_OPTIONS.map((o) => o.value)).toEqual([
      'major', 'minor', 'dorian', 'phrygian', 'lydian', 'mixolydian', 'locrian',
    ]);
    expect(MODE_OPTIONS.find((o) => o.value === 'dorian')?.label).toBe('Dorian');
    expect(DEFAULT_MODE).toBe('major');
  });

  it('renders all mode options on focus with capitalized labels', () => {
    render(<ModePicker value="major" onChange={vi.fn()} />);
    const input = screen.getByTestId('mode-picker-input');
    fireEvent.focus(input);
    expect(screen.getByTestId('mode-picker-option-mixolydian')).toHaveTextContent('Mixolydian');
  });

  it('calls onChange with the lowercase mode value when selected', () => {
    const onChange = vi.fn();
    render(<ModePicker value="major" onChange={onChange} />);
    const input = screen.getByTestId('mode-picker-input');
    fireEvent.focus(input);
    fireEvent.mouseDown(screen.getByTestId('mode-picker-option-dorian'));
    expect(onChange).toHaveBeenCalledWith('dorian');
  });

  it('selects via keyboard (ArrowDown + Enter)', () => {
    const onChange = vi.fn();
    render(<ModePicker value="major" onChange={onChange} />);
    const input = screen.getByTestId('mode-picker-input');
    fireEvent.focus(input);
    fireEvent.keyDown(input, { key: 'ArrowDown' }); // major -> minor
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith('minor');
  });

  it('filters case-insensitively over the label', () => {
    render(<ModePicker value="major" onChange={vi.fn()} />);
    const input = screen.getByTestId('mode-picker-input');
    fireEvent.change(input, { target: { value: 'lyd' } });
    expect(screen.getByTestId('mode-picker-option-lydian')).toBeInTheDocument();
    expect(screen.queryByTestId('mode-picker-option-minor')).not.toBeInTheDocument();
  });

  it('shows the capitalized label for the selected mode', () => {
    render(<ModePicker value="phrygian" onChange={vi.fn()} />);
    expect(screen.getByTestId('mode-picker-input')).toHaveValue('Phrygian');
  });
});
