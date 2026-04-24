import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { StarButton } from '../StarButton';

describe('StarButton', () => {
  it('renders outlined star when uncurated', () => {
    render(<StarButton isCurated={false} onToggle={vi.fn()} />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-pressed', 'false');
    expect(btn).toHaveAttribute('aria-label', 'Mark as curated');
    expect(btn).not.toHaveAttribute('aria-disabled', 'true');
  });

  it('renders filled star when curated', () => {
    render(<StarButton isCurated={true} onToggle={vi.fn()} />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-pressed', 'true');
    expect(btn).toHaveAttribute('aria-label', 'Remove from curated');
  });

  it('renders disabled star when isCurated is null', () => {
    render(<StarButton isCurated={null} onToggle={vi.fn()} />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-disabled', 'true');
    expect(btn).toHaveAttribute('title', 'Available after the round completes');
  });

  it('calls onToggle with inverted state on click', () => {
    const onToggle = vi.fn();
    render(<StarButton isCurated={false} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onToggle).toHaveBeenCalledWith(true);
  });

  it('does not call onToggle when disabled', () => {
    const onToggle = vi.fn();
    render(<StarButton isCurated={null} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onToggle).not.toHaveBeenCalled();
  });
});
