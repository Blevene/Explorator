import OptionPicker from './OptionPicker';
import { KEY_OPTIONS } from './musicOptions';

interface KeyPickerProps {
  value: string;
  onChange: (key: string) => void;
  disabled?: boolean;
  compact?: boolean;
}

/** Picker over the fixed list of musical keys. Emits the key string. */
export default function KeyPicker({ value, onChange, disabled, compact }: KeyPickerProps) {
  return (
    <OptionPicker
      value={value}
      onChange={onChange}
      options={KEY_OPTIONS}
      ariaLabel="Key"
      testIdPrefix="key-picker"
      disabled={disabled}
      compact={compact}
    />
  );
}
