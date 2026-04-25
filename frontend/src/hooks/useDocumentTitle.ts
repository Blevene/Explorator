import { useEffect } from 'react';

const SUFFIX = 'Explorator';

/**
 * Set document.title for the lifetime of the calling component.
 * Restores the previous title on unmount.
 *
 * Example:
 *   useDocumentTitle('Genres')   // -> "Genres — Explorator"
 *   useDocumentTitle(null)       // -> "Explorator" (no prefix)
 */
export function useDocumentTitle(title: string | null | undefined) {
  useEffect(() => {
    const previous = document.title;
    document.title = title ? `${title} — ${SUFFIX}` : SUFFIX;
    return () => {
      document.title = previous;
    };
  }, [title]);
}
