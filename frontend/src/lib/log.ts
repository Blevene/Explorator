/**
 * Dev-only error logging.
 *
 * Production builds drop console output to keep the user's devtools
 * uncluttered when the app fails non-critically (a stale fetch, a
 * cancelled request). In dev, errors are logged with a stable context
 * prefix so they're easy to find while debugging.
 *
 * For errors users need to *know* about, prefer a toast or an inline
 * alert; this helper is for the developer-only "what just happened?"
 * channel.
 */
export function logError(context: string, err: unknown): void {
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.error(`[${context}]`, err);
  }
}
