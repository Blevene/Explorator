import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import Dialog from '../Dialog';

beforeEach(() => {
  document.body.style.overflow = '';
});

afterEach(() => {
  cleanup();
});

describe('Dialog', () => {
  it('renders children inside a role="dialog" panel with aria-modal', () => {
    render(
      <Dialog onClose={() => {}} labelledBy="title">
        <h2 id="title">Hello</h2>
        <button>OK</button>
      </Dialog>,
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'title');
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('closes on Escape', () => {
    const onClose = vi.fn();
    render(
      <Dialog onClose={onClose}>
        <button>OK</button>
      </Dialog>,
    );
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes when the backdrop is clicked', () => {
    const onClose = vi.fn();
    const { container } = render(
      <Dialog onClose={onClose}>
        <button>OK</button>
      </Dialog>,
    );
    const backdrop = container.firstChild as HTMLElement;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does NOT close when the panel itself is clicked', () => {
    const onClose = vi.fn();
    render(
      <Dialog onClose={onClose}>
        <button>OK</button>
      </Dialog>,
    );
    fireEvent.click(screen.getByRole('dialog'));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('does not close on backdrop click when closeOnBackdropClick=false', () => {
    const onClose = vi.fn();
    const { container } = render(
      <Dialog onClose={onClose} closeOnBackdropClick={false}>
        <button>OK</button>
      </Dialog>,
    );
    fireEvent.click(container.firstChild as HTMLElement);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('locks body scroll while open and restores on unmount', () => {
    document.body.style.overflow = 'auto';
    const { unmount } = render(
      <Dialog onClose={() => {}}>
        <button>OK</button>
      </Dialog>,
    );
    expect(document.body.style.overflow).toBe('hidden');
    unmount();
    expect(document.body.style.overflow).toBe('auto');
  });

  it('moves focus to the first focusable child on mount', () => {
    render(
      <Dialog onClose={() => {}}>
        <button>First</button>
        <button>Second</button>
      </Dialog>,
    );
    expect(document.activeElement).toBe(screen.getByText('First'));
  });

  it('restores focus to the previously focused element on unmount', () => {
    const trigger = document.createElement('button');
    trigger.textContent = 'Trigger';
    document.body.appendChild(trigger);
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    const { unmount } = render(
      <Dialog onClose={() => {}}>
        <button>Inside</button>
      </Dialog>,
    );
    expect(document.activeElement).toBe(screen.getByText('Inside'));
    unmount();
    expect(document.activeElement).toBe(trigger);
    document.body.removeChild(trigger);
  });
});
