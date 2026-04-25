import { useEffect, useRef, type ReactNode, type RefObject, type CSSProperties } from 'react';

type Placement = 'center' | 'right';

interface DialogProps {
  onClose: () => void;
  labelledBy?: string;
  label?: string;
  placement?: Placement;
  closeOnBackdropClick?: boolean;
  panelClassName?: string;
  panelStyle?: CSSProperties;
  children: ReactNode;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

function useDialogBehavior(panelRef: RefObject<HTMLDivElement | null>, onClose: () => void) {
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const panel = panelRef.current;
    if (panel && !panel.contains(document.activeElement)) {
      const first = panel.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
      (first ?? panel).focus();
    }

    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key === 'Tab' && panelRef.current) {
        const focusables = Array.from(
          panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
        ).filter((el) => el.offsetParent !== null);
        if (focusables.length === 0) {
          e.preventDefault();
          panelRef.current.focus();
          return;
        }
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        const active = document.activeElement;
        if (e.shiftKey && (active === first || !panelRef.current.contains(active))) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && (active === last || !panelRef.current.contains(active))) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.body.style.overflow = prevOverflow;
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
        previouslyFocused.focus();
      }
    };
  }, [onClose, panelRef]);
}

export default function Dialog({
  onClose,
  labelledBy,
  label,
  placement = 'center',
  closeOnBackdropClick = true,
  panelClassName = '',
  panelStyle,
  children,
}: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  useDialogBehavior(panelRef, onClose);

  const wrapperClass =
    placement === 'right'
      ? 'fixed inset-0 z-50 flex justify-end'
      : 'fixed inset-0 z-50 flex items-center justify-center';

  return (
    <div
      className={wrapperClass}
      style={{ background: 'var(--overlay-backdrop)' }}
      onClick={closeOnBackdropClick ? onClose : undefined}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-label={label}
        tabIndex={-1}
        className={panelClassName}
        style={panelStyle}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
