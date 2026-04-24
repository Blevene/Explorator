import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PatternFilters } from '../PatternFilters';
import { usePatternFiltersStore } from '../../../stores/patternFiltersStore';

describe('PatternFilters curated-only', () => {
  beforeEach(() => {
    usePatternFiltersStore.setState({ filters: {} });
  });

  it('renders a Curated only checkbox, unchecked by default', () => {
    render(<PatternFilters />);
    const cb = screen.getByLabelText('Curated only') as HTMLInputElement;
    expect(cb).toBeInTheDocument();
    expect(cb.checked).toBe(false);
  });

  it('toggling the checkbox calls setCuratedOnly', () => {
    render(<PatternFilters />);
    const cb = screen.getByLabelText('Curated only') as HTMLInputElement;
    fireEvent.click(cb);
    expect(usePatternFiltersStore.getState().filters.curated_only).toBe(true);
    fireEvent.click(cb);
    expect(usePatternFiltersStore.getState().filters.curated_only).toBeUndefined();
  });
});
