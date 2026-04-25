import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getGenreDetail } from '../services/api';

export interface UseGenreDetailDrawerResult {
  /** The fetched genre detail, or null when no drawer is open or fetch hasn't completed. */
  genre: Record<string, any> | null;
  /** True while a fetch is in flight. */
  loading: boolean;
  /** Open the drawer for a given genre slug (writes ?detail=<slug> to URL). */
  open: (slug: string) => void;
  /** Close the drawer (removes ?detail from URL). */
  close: () => void;
}

/**
 * Drawer state lives in the URL (?detail=<slug>) so it's shareable,
 * restoreable on reload, and closes naturally with browser-back. The
 * hook owns:
 *   - reading/writing the detail slug from the URL,
 *   - hydrating the genre detail when the slug changes,
 *   - cancellation of in-flight fetches when the slug changes again,
 *   - silently stripping a bad slug from the URL on 404 (so a stale link
 *     doesn't strand the user on a broken page).
 *
 * `replace: true` on the bad-slug strip is deliberate: a user clicking
 * Back after a 404 should land on whatever page they came from, not
 * back on the broken URL.
 */
export function useGenreDetailDrawer(): UseGenreDetailDrawerResult {
  const [searchParams, setSearchParams] = useSearchParams();
  const slug = searchParams.get('detail');
  const [genre, setGenre] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!slug) {
      setGenre(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    getGenreDetail(slug)
      .then((detail) => { if (!cancelled) setGenre(detail); })
      .catch(() => {
        if (!cancelled) {
          setGenre(null);
          setSearchParams((prev) => {
            const next = new URLSearchParams(prev);
            next.delete('detail');
            return next;
          }, { replace: true });
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [slug, setSearchParams]);

  const open = (newSlug: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('detail', newSlug);
      return next;
    });
  };

  const close = () => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete('detail');
      return next;
    });
  };

  return { genre, loading, open, close };
}
