import OptionPicker from './OptionPicker';
import { MODE_OPTIONS } from './musicOptions';

interface ModePickerProps {
  value: string;
  onChange: (musicalMode: string) => void;
  disabled?: boolean;
  compact?: boolean;
}

/** Picker over the fixed list of musical modes. Emits the lowercase mode. */
export default function ModePicker({ value, onChange, disabled, compact }: ModePickerProps) {
  return (
    <OptionPicker
      value={value}
      onChange={onChange}
      options={MODE_OPTIONS}
      ariaLabel="Mode"
      testIdPrefix="mode-picker"
      disabled={disabled}
      compact={compact}
    />
  );
}
