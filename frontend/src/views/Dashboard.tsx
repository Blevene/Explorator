import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createSession, listSessions, getGenres } from '../services/api';
import type { GenreSummary } from '../services/api';
import GenrePicker from '../components/GenrePicker';
import KeyPicker from '../components/KeyPicker';
import ModePicker from '../components/ModePicker';
import { DEFAULT_KEY, DEFAULT_MODE } from '../components/musicOptions';
import LimitedModeBanner from '../components/LimitedModeBanner';
import { useSessionStore } from '../stores/sessionStore';
import { useCan, useIsMemoryMode } from '../stores/capabilitiesStore';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { logError } from '../lib/log';

export default function Dashboard() {
  useDocumentTitle(null);
  const { sessions, setSessions } = useSessionStore();
  const canPatternLibrary = useCan('pattern_library');
  const isMemoryMode = useIsMemoryMode();
  const [prompt, setPrompt] = useState('');
  const [genres, setGenres] = useState<GenreSummary[]>([]);
  const [genre, setGenre] = useState('');
  const [key, setKey] = useState(DEFAULT_KEY);
  const [musicalMode, setMusicalMode] = useState(DEFAULT_MODE);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    listSessions()
      .then((data) => setSessions(data.items))
      .catch((err) => logError('Dashboard.listSessions', err));
  }, [setSessions]);

  useEffect(() => {
    getGenres()
      .then((items) => setGenres(items))
      .catch((err) => logError('Dashboard.getGenres', err));
  }, []);

  const handleCreate = async () => {
    if (!genre) return;
    setLoading(true);
    try {
      const session = await createSession(genre, key, musicalMode, prompt);
      navigate(`/session/${session.session_id}`);
    } catch (err) {
      logError('Dashboard.createSession', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-dvh flex flex-col">
      {isMemoryMode && <LimitedModeBanner />}
      {/* Hero */}
      <div className="flex-1 flex flex-col items-center justify-center px-8 pb-16 pt-24">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-light tracking-tight mb-2" style={{ color: 'var(--text-primary)' }}>
            <span className="font-semibold" style={{ color: 'var(--accent-primary)' }}>Explorator</span>
          </h1>
          <p className="text-sm tracking-widest uppercase" style={{ color: 'var(--text-muted)' }}>
            Genre-Aware Musical Exploration
          </p>
          <div className="mt-4 flex gap-4 justify-center">
            <a
              href="/genres"
              className="text-xs tracking-wider uppercase transition-colors text-[var(--text-muted)] hover:text-[var(--accent-primary)] focus-visible:text-[var(--accent-primary)]"
            >
              Manage Genres &rarr;
            </a>
            {canPatternLibrary && (
              <a
                href="/patterns"
                className="text-xs tracking-wider uppercase transition-colors text-[var(--text-muted)] hover:text-[var(--accent-primary)] focus-visible:text-[var(--accent-primary)]"
              >
                Pattern Library &rarr;
              </a>
            )}
          </div>
        </div>

        {/* Create session */}
        <div className="w-full max-w-xl">
          <div
            className="rounded-xl p-px"
            style={{ background: `linear-gradient(135deg, var(--border-subtle), var(--border-default), var(--border-subtle))` }}
          >
            <div className="rounded-xl p-5 flex flex-col gap-3" style={{ background: 'var(--surface-2)' }}>
              {/* Genre / key / mode pickers share one row as equal columns that
                  shrink to fit — the mood input keeps full width on its own row. */}
              <div className="grid grid-cols-3 gap-2">
                <GenrePicker value={genre} onChange={setGenre} genres={genres} />
                <KeyPicker value={key} onChange={setKey} />
                <ModePicker value={musicalMode} onChange={setMusicalMode} />
              </div>
              {/* Mood / feeling input + Explore */}
              <div className="flex flex-col sm:flex-row gap-3">
                <input
                  type="text"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                  placeholder="mood, feeling, customization (optional)…"
                  aria-label="Session prompt"
                  className="flex-1 min-w-0 px-4 py-2.5 rounded-lg text-sm placeholder-opacity-40 focus:outline-none transition-colors"
                  style={{
                    background: 'var(--surface-1)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)',
                  }}
                />
                <button
                  onClick={handleCreate}
                  disabled={loading || !genre}
                  className="px-6 py-2.5 rounded-lg font-medium text-sm transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                  style={{
                    background: 'var(--accent-primary)',
                    color: 'var(--surface-0)',
                  }}
                >
                  {loading ? 'Creating...' : 'Explore'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Session list */}
      <div className="max-w-xl mx-auto w-full px-8 pb-12">
        <h2
          className="text-xs font-medium uppercase tracking-widest mb-3"
          style={{ color: 'var(--text-muted)' }}
        >
          Recent Sessions
        </h2>
        {sessions.length > 0 ? (
          <div className="flex flex-col gap-1.5">
            {sessions.map((s) => (
              <button
                key={s.session_id}
                type="button"
                onClick={() => navigate(`/session/${s.session_id}`)}
                className="flex justify-between items-center w-full text-left px-4 py-3 rounded-lg cursor-pointer transition-colors bg-[var(--surface-2)] hover:bg-[var(--surface-3)] focus-visible:bg-[var(--surface-3)]"
              >
                <span className="text-sm truncate mr-4" style={{ color: 'var(--text-primary)' }}>
                  {s.prompt || 'Untitled session'}
                </span>
                <span
                  className="text-xs font-mono shrink-0"
                  style={{ color: 'var(--text-muted)' }}
                >
                  {s.status}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <p
            className="text-xs px-4 py-3 rounded-lg"
            style={{
              color: 'var(--text-muted)',
              background: 'var(--surface-2)',
              border: '1px dashed var(--border-subtle)',
            }}
          >
            Sessions you create will appear here.
          </p>
        )}
      </div>
    </div>
  );
}
