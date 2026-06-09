import type { PickerOption } from './OptionPicker';

/** Canonical key spellings the backend accepts (display = value). */
export const KEY_OPTIONS: PickerOption[] = [
  'C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B',
].map((k) => ({ value: k, label: k }));

export const DEFAULT_KEY = 'C';

/** Musical modes the backend accepts. Value = lowercase; label = capitalized. */
export const MODE_OPTIONS: PickerOption[] = [
  'major', 'minor', 'dorian', 'phrygian', 'lydian', 'mixolydian', 'locrian',
].map((m) => ({ value: m, label: m.charAt(0).toUpperCase() + m.slice(1) }));

export const DEFAULT_MODE = 'major';
