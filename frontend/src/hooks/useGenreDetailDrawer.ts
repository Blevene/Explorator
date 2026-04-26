import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getGenreDetail, type GenreDetail } from '../services/api';

export interface UseGenreDetailDrawerResult {
  /** The fetched genre detail, or null when no drawer is open or fetch hasn't completed. */
  genre: GenreDetail | null;
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
  const [fetched, setFetched] = useState<GenreDetail | null>(null);
  const [loading, setLoading] = useState(false);

  // Derive `genre` and the in-flight loading flag from `slug` so that closing
  // the drawer (slug -> null) doesn't require a synchronous setState in an
  // effect. The fetch effect below only runs when slug is truthy.
  const genre = slug ? fetched : null;
  const effectiveLoading = slug ? loading : false;

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    // Sync external (network) state into the loading flag — legitimate
    // "external -> UI" pattern the rule's docs explicitly allow.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    getGenreDetail(slug)
      .then((detail) => { if (!cancelled) setFetched(detail); })
      .catch(() => {
        if (!cancelled) {
          setFetched(null);
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

  return { genre, loading: effectiveLoading, open, close };
}
