import { useEffect, useState } from 'react';
import { getGenreDetail } from '../services/api';
import { useGenreResearchStore } from '../stores/genreResearchStore';

const GENRE_COLORS: Record<string, string> = {
  dream_pop: 'var(--genre-dream-pop)',
  synthwave: 'var(--genre-synthwave)',
  cinematic: 'var(--genre-cinematic)',
};

const ACCENT_CYCLE = [
  'var(--genre-accent-1)',
  'var(--genre-accent-2)',
  'var(--genre-accent-3)',
  'var(--genre-accent-4)',
  'var(--genre-accent-5)',
];

function genreColor(slug: string, index: number): string {
  return GENRE_COLORS[slug] ?? ACCENT_CYCLE[index % ACCENT_CYCLE.length];
}

function toSnakeCase(s: string): string {
  return s
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');
}

const STEP_LABELS = ['Research', 'Draft', 'Critique', 'Refine', 'Validate'];
const STATUS_TO_STEP: Record<string, number> = {
  researching: 1,
  drafting: 2,
  critiquing: 3,
  refining: 4,
  validating: 5,
};

type ViewState = 'library' | 'progress' | 'review';

// ─── Helpers for rendering genre detail ─────────────────────────────────

function TagPills({ items, color }: { items: string[]; color?: string }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full px-2 py-0.5 text-[11px] font-mono"
          style={{ background: 'var(--surface-4)', color: color ?? 'var(--text-secondary)' }}
        >
          {item}
        </span>
      ))}
    </div>
  );
}

function LabeledValue({ label, value }: { label: string; value: string | number | boolean }) {
  return (
    <div className="flex justify-between items-center py-1">
      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
        {String(value)}
      </span>
    </div>
  );
}

function EnvelopeBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="py-1">
      <div className="flex justify-between mb-0.5">
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
        <span className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>{value.toFixed(2)}</span>
      </div>
      <div className="h-1.5 rounded-full" style={{ background: 'var(--surface-4)' }}>
        <div
          className="h-full rounded-full score-bar-animated"
          style={{
            width: `${Math.min(value * 100, 100)}%`,
            background: value > 0.6 ? 'var(--score-high)' : value > 0.3 ? 'var(--score-mid)' : 'var(--accent-secondary)',
          }}
        />
      </div>
    </div>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      className="rounded-xl p-4"
      style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
    >
      <h3
        className="text-[11px] font-semibold uppercase tracking-wider mb-3"
        style={{ color: 'var(--text-muted)' }}
      >
        {title}
      </h3>
      {children}
    </div>
  );
}

function DictSection({ title, data }: { title: string; data: Record<string, any> }) {
  if (!data || typeof data !== 'object') return null;
  return (
    <SectionCard title={title}>
      {Object.entries(data).map(([k, v]) => (
        <LabeledValue key={k} label={k.replace(/_/g, ' ')} value={v} />
      ))}
    </SectionCard>
  );
}

function GenreDetailDrawer({ genre, onClose }: { genre: Record<string, any>; onClose: () => void }) {
  const g = genre;
  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        style={{ background: 'var(--overlay-backdrop)' }}
        onClick={onClose}
      />
      {/* Drawer panel — slides in from right */}
      <div
        className="fixed top-0 right-0 z-50 h-full overflow-y-auto"
        style={{
          width: '480px',
          maxWidth: '90vw',
          background: 'var(--surface-1)',
          borderLeft: '1px solid var(--border-default)',
          animation: 'drawer-slide-in 200ms ease-out both',
        }}
      >
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                {g.display_name || g.genre}
              </h2>
              <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                {g.genre} &middot; v{g.version ?? 1}
              </span>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-xs transition-colors"
              style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}
            >
              &times;
            </button>
          </div>

          {/* Sections — single column in drawer */}
          <div className="flex flex-col gap-3">
        {/* Harmonic Vocabulary */}
        {Array.isArray(g.harmonic_vocabulary) && g.harmonic_vocabulary.length > 0 && (
          <SectionCard title="Harmonic Vocabulary">
            <TagPills items={g.harmonic_vocabulary} color="var(--accent-secondary)" />
          </SectionCard>
        )}

        {/* Harmonic Tendencies */}
        {g.harmonic_tendencies && <DictSection title="Harmonic Tendencies" data={g.harmonic_tendencies} />}

        {/* Voicing Tendencies */}
        {g.voicing_tendencies && <DictSection title="Voicing Tendencies" data={g.voicing_tendencies} />}

        {/* Bass Tendencies */}
        {g.bass_tendencies && <DictSection title="Bass Tendencies" data={g.bass_tendencies} />}

        {/* Groove Tendencies */}
        {g.groove_tendencies && <DictSection title="Groove Tendencies" data={g.groove_tendencies} />}

        {/* Melodic Tendencies */}
        {g.melodic_tendencies && typeof g.melodic_tendencies === 'object' && Object.keys(g.melodic_tendencies).length > 0 && (
          <DictSection title="Melodic Tendencies" data={g.melodic_tendencies} />
        )}

        {/* Voicing Preferences */}
        {g.voicing_preferences && (
          <SectionCard title="Voicing Preferences">
            {Object.entries(g.voicing_preferences).map(([k, v]) =>
              Array.isArray(v) ? (
                <div key={k} className="py-1">
                  <span className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>{k.replace(/_/g, ' ')}</span>
                  <TagPills items={v as string[]} />
                </div>
              ) : (
                <LabeledValue key={k} label={k.replace(/_/g, ' ')} value={v as string | number | boolean} />
              ),
            )}
          </SectionCard>
        )}

        {/* Bass Preferences */}
        {g.bass_preferences && (
          <SectionCard title="Bass Preferences">
            {Object.entries(g.bass_preferences).map(([k, v]) =>
              Array.isArray(v) ? (
                <div key={k} className="py-1">
                  <span className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>{k.replace(/_/g, ' ')}</span>
                  <TagPills items={v as string[]} />
                </div>
              ) : (
                <LabeledValue key={k} label={k.replace(/_/g, ' ')} value={v as string | number | boolean} />
              ),
            )}
          </SectionCard>
        )}

        {/* Experimentation Envelope */}
        {g.experimentation_envelope && (
          <SectionCard title="Experimentation Envelope">
            {Object.entries(g.experimentation_envelope).map(([k, v]) => (
              <EnvelopeBar key={k} label={k.replace(/_/g, ' ')} value={v as number} />
            ))}
          </SectionCard>
        )}

        {/* Common Devices */}
        {Array.isArray(g.common_devices) && g.common_devices.length > 0 && (
          <SectionCard title="Common Devices">
            <ul className="space-y-1">
              {g.common_devices.map((d: string, i: number) => (
                <li key={i} className="text-xs flex items-start gap-2" style={{ color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--accent-primary)' }}>&#x2022;</span>
                  {d}
                </li>
              ))}
            </ul>
          </SectionCard>
        )}
          </div>
        </div>
      </div>
    </>
  );
}

export default function GenreManagement() {
  const {
    genres,
    pendingDrafts,
    activeJobId,
    activeJobStatus,
    progressDetail,
    errorMessage,
    reviewDraft,
    fetchGenres,
    fetchDrafts,
    startResearch,
    fetchDraftDetail,
    doApproveDraft,
    doRejectDraft,
    reset,
  } = useGenreResearchStore();

  const [view, setView] = useState<ViewState>('library');
  const [showForm, setShowForm] = useState(false);
  const [genreName, setGenreName] = useState('');
  const [refArtists, setRefArtists] = useState('');
  const [rejectMode, setRejectMode] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [expandResearchLog, setExpandResearchLog] = useState(false);
  const [expandCritique, setExpandCritique] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [selectedGenre, setSelectedGenre] = useState<Record<string, any> | null>(null);
  const [loadingGenre, setLoadingGenre] = useState(false);

  const handleGenreClick = async (genreSlug: string) => {
    setLoadingGenre(true);
    try {
      const detail = await getGenreDetail(genreSlug);
      setSelectedGenre(detail);
    } catch {
      setSelectedGenre(null);
    } finally {
      setLoadingGenre(false);
    }
  };

  useEffect(() => {
    fetchGenres().catch(console.error);
    fetchDrafts().catch(console.error);
  }, [fetchGenres, fetchDrafts]);

  // Auto-transition to progress view when research starts
  useEffect(() => {
    if (activeJobId && activeJobStatus && activeJobStatus !== 'pending_review' && activeJobStatus !== 'failed') {
      setView('progress');
    }
    if (activeJobStatus === 'pending_review' && activeJobId) {
      // Auto-open review for the just-completed job
      fetchDraftDetail(activeJobId).then(() => {
        setRejectMode(false);
        setRejectReason('');
        setExpandResearchLog(false);
        setExpandCritique(false);
        setView('review');
      }).catch(() => {
        // Fallback to library if fetch fails
        setView('library');
        reset();
        fetchDrafts().catch(console.error);
      });
    }
  }, [activeJobId, activeJobStatus, reset, fetchDrafts, fetchDraftDetail]);

  const handleStartResearch = async () => {
    if (!genreName.trim()) return;
    setSubmitError(null);
    const artists = refArtists
      .split('\n')
      .map((a) => a.trim())
      .filter(Boolean);
    try {
      await startResearch(genreName.trim(), artists);
      setShowForm(false);
      setGenreName('');
      setRefArtists('');
    } catch (err: any) {
      setSubmitError(err.message || 'Failed to start research');
    }
  };

  const handleOpenReview = async (jobId: string) => {
    await fetchDraftDetail(jobId);
    setRejectMode(false);
    setRejectReason('');
    setExpandResearchLog(false);
    setExpandCritique(false);
    setView('review');
  };

  const handleApprove = async () => {
    if (!reviewDraft) return;
    await doApproveDraft(reviewDraft.id);
    setView('library');
  };

  const handleReject = async () => {
    if (!reviewDraft) return;
    await doRejectDraft(reviewDraft.id, rejectReason);
    setRejectMode(false);
    setRejectReason('');
    setView('library');
  };

  const handleBackToLibrary = () => {
    reset();
    setView('library');
  };

  // ─── View 1: Genre Library ───────────────────────────────────────────

  if (view === 'library') {
    return (
      <div className="min-h-screen px-8 py-12 max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-10">
          <h1
            className="text-4xl font-light tracking-tight mb-1"
            style={{ color: 'var(--text-primary)' }}
          >
            <span className="font-semibold" style={{ color: 'var(--accent-primary)' }}>
              Genres
            </span>
          </h1>
          <p
            className="text-sm tracking-widest uppercase"
            style={{ color: 'var(--text-muted)' }}
          >
            Genre library &amp; research
          </p>
        </div>

        {/* Actions */}
        <div className="mb-8 flex items-center gap-4">
          <button
            onClick={() => setShowForm((v) => !v)}
            className="px-5 py-2 rounded-lg font-medium text-sm transition-all"
            style={{ background: 'var(--accent-primary)', color: 'var(--surface-0)' }}
          >
            Research New Genre
          </button>
          <a
            href="/"
            className="text-xs tracking-wider uppercase transition-colors"
            style={{ color: 'var(--text-muted)' }}
            onMouseOver={(e) => (e.currentTarget.style.color = 'var(--accent-primary)')}
            onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            &larr; Dashboard
          </a>
        </div>

        {/* Inline request form */}
        {showForm && (
          <div
            className="rounded-xl p-5 mb-8 card-animated"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
          >
            <div className="flex flex-col gap-3">
              <div>
                <label className="text-xs font-medium uppercase tracking-wider mb-1 block" style={{ color: 'var(--text-muted)' }}>
                  Genre Name
                </label>
                <input
                  type="text"
                  value={genreName}
                  onChange={(e) => setGenreName(e.target.value)}
                  placeholder="e.g. Shoegaze"
                  className="w-full px-4 py-2.5 rounded-lg text-sm focus:outline-none transition-colors"
                  style={{
                    background: 'var(--surface-1)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)',
                  }}
                />
                {genreName.trim() && (
                  <span className="font-mono text-xs mt-1 block" style={{ color: 'var(--text-muted)' }}>
                    slug: {toSnakeCase(genreName)}
                  </span>
                )}
              </div>
              <div>
                <label className="text-xs font-medium uppercase tracking-wider mb-1 block" style={{ color: 'var(--text-muted)' }}>
                  Reference Artists (one per line)
                </label>
                <textarea
                  value={refArtists}
                  onChange={(e) => setRefArtists(e.target.value)}
                  placeholder={'My Bloody Valentine\nSlowdive\nCocteau Twins'}
                  rows={3}
                  className="w-full px-4 py-2.5 rounded-lg text-sm focus:outline-none transition-colors resize-none"
                  style={{
                    background: 'var(--surface-1)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)',
                  }}
                />
              </div>
              {submitError && (
                <p className="text-xs" style={{ color: 'var(--score-low)' }}>{submitError}</p>
              )}
              <button
                onClick={handleStartResearch}
                disabled={!genreName.trim()}
                className="self-start px-5 py-2 rounded-lg font-medium text-sm transition-all disabled:opacity-30"
                style={{ background: 'var(--accent-primary)', color: 'var(--surface-0)' }}
              >
                Start Research
              </button>
            </div>
          </div>
        )}

        {/* Pending drafts */}
        {pendingDrafts.length > 0 && (
          <div className="mb-6">
            <h2
              className="text-xs font-medium uppercase tracking-widest mb-3"
              style={{ color: 'var(--text-muted)' }}
            >
              Pending Review
            </h2>
            <div className="flex flex-col gap-2">
              {pendingDrafts.map((d) => (
                <div
                  key={d.job_id}
                  onClick={() => handleOpenReview(d.job_id)}
                  className="flex items-center justify-between px-4 py-3 rounded-xl cursor-pointer transition-colors card-interactive"
                  style={{
                    background: 'var(--surface-2)',
                    borderTop: '1px solid var(--border-subtle)',
                    borderRight: '1px solid var(--border-subtle)',
                    borderBottom: '1px solid var(--border-subtle)',
                    borderLeft: '3px solid var(--accent-primary)',
                  }}
                >
                  <span className="text-sm" style={{ color: 'var(--text-primary)' }}>
                    {d.genre_name}
                  </span>
                  <span
                    className="text-[11px] font-medium px-2 py-0.5 rounded-full"
                    style={{ background: 'var(--accent-primary-dim)', color: 'var(--accent-primary)' }}
                  >
                    Pending Review
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Genre library cards */}
        {genres.length > 0 && (
          <div>
            <h2
              className="text-xs font-medium uppercase tracking-widest mb-3"
              style={{ color: 'var(--text-muted)' }}
            >
              Installed Genres
            </h2>
            <div className="flex flex-col gap-2">
              {genres.map((g, i) => (
                <div
                  key={g.genre}
                  onClick={() => handleGenreClick(g.genre)}
                  className="px-4 py-3 rounded-xl card-animated cursor-pointer card-interactive"
                  style={{
                    background: selectedGenre?.genre === g.genre ? 'var(--surface-3)' : 'var(--surface-2)',
                    borderTop: `1px solid ${selectedGenre?.genre === g.genre ? 'var(--border-bright)' : 'var(--border-subtle)'}`,
                    borderRight: `1px solid ${selectedGenre?.genre === g.genre ? 'var(--border-bright)' : 'var(--border-subtle)'}`,
                    borderBottom: `1px solid ${selectedGenre?.genre === g.genre ? 'var(--border-bright)' : 'var(--border-subtle)'}`,
                    borderLeft: `3px solid ${genreColor(g.genre, i)}`,
                    animationDelay: `${i * 50}ms`,
                  }}
                >
                  <span className="text-sm" style={{ color: 'var(--text-primary)' }}>
                    {g.display_name}
                  </span>
                  <span
                    className="font-mono text-xs ml-3"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    {g.genre}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {genres.length === 0 && pendingDrafts.length === 0 && !showForm && (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            No genres installed yet. Research your first genre to get started.
          </p>
        )}

        {/* Genre detail drawer — fixed overlay, not inline */}
        {selectedGenre && !loadingGenre && (
          <GenreDetailDrawer genre={selectedGenre} onClose={() => setSelectedGenre(null)} />
        )}
      </div>
    );
  }

  // ─── View 2: Research In-Progress ────────────────────────────────────

  if (view === 'progress') {
    const currentStep = STATUS_TO_STEP[activeJobStatus ?? ''] ?? 0;
    const isFailed = activeJobStatus === 'failed';

    return (
      <div className="min-h-screen px-8 py-12 max-w-3xl mx-auto">
        <div className="mb-10">
          <h1
            className="text-4xl font-light tracking-tight mb-1"
            style={{ color: 'var(--text-primary)' }}
          >
            <span className="font-semibold" style={{ color: 'var(--accent-primary)' }}>
              Researching
            </span>
          </h1>
          <p className="text-sm tracking-widest uppercase" style={{ color: 'var(--text-muted)' }}>
            Genre research in progress
          </p>
        </div>

        {/* Step rail */}
        <div className="flex items-center justify-center gap-0 mb-10">
          {STEP_LABELS.map((label, i) => {
            const stepNum = i + 1;
            const isCompleted = stepNum < currentStep;
            const isActive = stepNum === currentStep;

            let circleBg = 'var(--surface-3)';
            let circleBorder = 'var(--border-subtle)';
            let textColor = 'var(--text-muted)';

            if (isCompleted) {
              circleBg = 'var(--accent-tertiary)';
              circleBorder = 'var(--accent-tertiary)';
              textColor = 'var(--accent-tertiary)';
            } else if (isActive && isFailed) {
              circleBg = 'var(--surface-3)';
              circleBorder = 'var(--score-low)';
              textColor = 'var(--score-low)';
            } else if (isActive) {
              circleBg = 'var(--surface-3)';
              circleBorder = 'var(--accent-primary)';
              textColor = 'var(--accent-primary)';
            }

            return (
              <div key={label} className="flex items-center">
                <div className="flex flex-col items-center">
                  <div
                    className={`flex items-center justify-center rounded-full ${isActive && !isFailed ? 'step-active' : ''}`}
                    style={{
                      width: 28,
                      height: 28,
                      background: circleBg,
                      border: `2px solid ${circleBorder}`,
                    }}
                  >
                    {isCompleted && (
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M3 7l3 3 5-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </div>
                  <span
                    className="text-[10px] mt-1.5 font-medium uppercase tracking-wider"
                    style={{ color: textColor }}
                  >
                    {label}
                  </span>
                </div>
                {/* Connecting line */}
                {i < STEP_LABELS.length - 1 && (
                  <div
                    className="mx-2"
                    style={{
                      width: 40,
                      height: 2,
                      background: isCompleted ? 'var(--accent-tertiary)' : 'var(--border-subtle)',
                      marginBottom: 18,
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>

        {/* Substep detail */}
        <div
          className="rounded-xl p-5"
          style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
        >
          <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--text-primary)' }}>
            {activeJobStatus ? activeJobStatus.charAt(0).toUpperCase() + activeJobStatus.slice(1) : 'Starting'}
          </h3>
          {progressDetail && (
            <p
              key={progressDetail}
              className="text-xs substep-update"
              style={{ color: 'var(--text-secondary)' }}
            >
              {progressDetail}
            </p>
          )}
        </div>

        {/* Error state */}
        {isFailed && (
          <div className="mt-6">
            <div
              className="rounded-xl p-4 mb-4"
              style={{ background: 'var(--surface-2)', border: '1px solid var(--score-low)' }}
            >
              <p className="text-sm" style={{ color: 'var(--score-low)' }}>
                {errorMessage || 'Research failed unexpectedly.'}
              </p>
            </div>
            <button
              onClick={handleBackToLibrary}
              className="px-5 py-2 rounded-lg font-medium text-sm transition-all"
              style={{ background: 'var(--surface-3)', color: 'var(--text-primary)' }}
            >
              Back to Library
            </button>
          </div>
        )}
      </div>
    );
  }

  // ─── View 3: Review View ─────────────────────────────────────────────

  if (view === 'review' && reviewDraft) {
    const draft = reviewDraft;
    const profile = draft.draft_yamls?.profile ?? {};
    const rules = draft.draft_yamls?.rules ?? {};
    const grammar = draft.draft_yamls?.grammar ?? {};
    const validationErrors = Array.isArray(draft.validation_errors) ? draft.validation_errors : [];
    const hasValidationErrors = validationErrors.length > 0;

    return (
      <div className="min-h-screen px-8 py-12 max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-1">
            <h1
              className="text-3xl font-light tracking-tight"
              style={{ color: 'var(--text-primary)' }}
            >
              <span className="font-semibold">{draft.genre_name}</span>
            </h1>
            <span
              className="text-[11px] font-medium px-2 py-0.5 rounded-full"
              style={{ background: 'var(--accent-primary-dim)', color: 'var(--accent-primary)' }}
            >
              Pending Review
            </span>
            {hasValidationErrors && (
              <span
                className="text-[11px] font-medium px-2 py-0.5 rounded-full"
                style={{ background: 'rgba(248,113,113,0.15)', color: 'var(--score-low)' }}
              >
                Validation Warnings
              </span>
            )}
          </div>
          <button
            onClick={handleBackToLibrary}
            className="text-xs tracking-wider uppercase transition-colors mt-2"
            style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer' }}
            onMouseOver={(e) => (e.currentTarget.style.color = 'var(--accent-primary)')}
            onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            &larr; Back to Library
          </button>
        </div>

        {/* Validation errors */}
        {hasValidationErrors && (
          <div
            className="rounded-xl p-4 mb-6"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--score-low)' }}
          >
            <h4 className="text-xs font-medium uppercase tracking-wider mb-2" style={{ color: 'var(--score-low)' }}>
              Validation Warnings
            </h4>
            <ul className="text-xs space-y-1" style={{ color: 'var(--text-secondary)' }}>
              {validationErrors.map((err: string, i: number) => (
                <li key={i}>• {err}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Three-column grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {/* Profile card */}
          <div
            className="rounded-xl p-4"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
          >
            <h3 className="text-xs font-medium uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
              Profile
            </h3>
            <p className="text-sm font-medium mb-3" style={{ color: 'var(--text-primary)' }}>
              {profile.display_name ?? draft.genre_name}
            </p>

            {/* Harmonic vocabulary tags */}
            {profile.harmonic_vocabulary && (
              <div className="mb-3">
                <span className="text-[10px] uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>
                  Harmonic Vocabulary
                </span>
                <div className="flex flex-wrap gap-1">
                  {(Array.isArray(profile.harmonic_vocabulary) ? profile.harmonic_vocabulary : []).map((v: string, i: number) => (
                    <span
                      key={i}
                      className="rounded-full px-2 py-0.5 text-[11px] font-mono"
                      style={{ background: 'var(--surface-4)', color: 'var(--text-secondary)' }}
                    >
                      {v}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Tendencies */}
            {profile.tendencies && (
              <div className="mb-3">
                <span className="text-[10px] uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>
                  Tendencies
                </span>
                {Object.entries(profile.tendencies as Record<string, any>).map(([k, v]) => (
                  <div key={k} className="flex justify-between text-xs mb-0.5">
                    <span style={{ color: 'var(--text-secondary)' }}>{k}</span>
                    <span className="font-mono" style={{ color: 'var(--text-primary)' }}>{String(v)}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Common devices */}
            {profile.common_devices && (
              <div className="mb-3">
                <span className="text-[10px] uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>
                  Common Devices
                </span>
                <ul className="text-xs space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
                  {(Array.isArray(profile.common_devices) ? profile.common_devices : []).map((d: string, i: number) => (
                    <li key={i}>• {d}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Experimentation envelope */}
            {profile.experimentation_envelope && (
              <div>
                <span className="text-[10px] uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>
                  Experimentation Envelope
                </span>
                {Object.entries(profile.experimentation_envelope as Record<string, number>).map(([k, v]) => (
                  <div key={k} className="mb-1">
                    <div className="flex justify-between text-[10px] mb-0.5">
                      <span style={{ color: 'var(--text-secondary)' }}>{k}</span>
                      <span className="font-mono" style={{ color: 'var(--text-primary)' }}>{v}</span>
                    </div>
                    <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--surface-4)' }}>
                      <div
                        className="h-full rounded-full score-bar-animated"
                        style={{
                          width: `${(typeof v === 'number' ? v : 0) * 100}%`,
                          background: 'var(--accent-secondary)',
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Rules card */}
          <div
            className="rounded-xl p-4"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
          >
            <h3 className="text-xs font-medium uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
              Rules
            </h3>

            {/* Rules list */}
            {rules.rules && (
              <div className="mb-4">
                {(Array.isArray(rules.rules) ? rules.rules : []).map((rule: any, i: number) => (
                  <div key={i} className="mb-2">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-xs" style={{ color: 'var(--text-primary)' }}>{rule.name}</span>
                      <span className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>{rule.type}</span>
                    </div>
                    {rule.weight != null && (
                      <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--surface-4)' }}>
                        <div
                          className="h-full rounded-full score-bar-animated"
                          style={{
                            width: `${(rule.weight ?? 0) * 100}%`,
                            background:
                              rule.weight >= 0.7
                                ? 'var(--score-high)'
                                : rule.weight >= 0.4
                                  ? 'var(--score-mid)'
                                  : 'var(--score-low)',
                          }}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Anti-patterns */}
            {rules.anti_patterns && (
              <div>
                <span className="text-[10px] uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>
                  Anti-patterns
                </span>
                {(Array.isArray(rules.anti_patterns) ? rules.anti_patterns : []).map((ap: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-xs mb-1">
                    <span
                      className="text-[10px] font-medium px-1.5 py-0.5 rounded"
                      style={{
                        background:
                          ap.severity === 'high'
                            ? 'rgba(248,113,113,0.15)'
                            : ap.severity === 'medium'
                              ? 'rgba(251,191,36,0.15)'
                              : 'rgba(85,94,116,0.15)',
                        color:
                          ap.severity === 'high'
                            ? 'var(--score-low)'
                            : ap.severity === 'medium'
                              ? 'var(--score-mid)'
                              : 'var(--text-muted)',
                      }}
                    >
                      {ap.severity}
                    </span>
                    <span style={{ color: 'var(--text-secondary)' }}>{ap.name ?? ap.pattern ?? String(ap)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Grammar card */}
          <div
            className="rounded-xl p-4"
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
          >
            <h3 className="text-xs font-medium uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
              Grammar
            </h3>

            {/* Chord qualities */}
            {grammar.chord_qualities && (
              <div className="mb-3">
                <span className="text-[10px] uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>
                  Chord Qualities
                </span>
                <div className="flex flex-wrap gap-1">
                  {(Array.isArray(grammar.chord_qualities) ? grammar.chord_qualities : []).map((q: string, i: number) => (
                    <span
                      key={i}
                      className="rounded-full px-2 py-0.5 text-[11px] font-mono"
                      style={{ background: 'var(--surface-4)', color: 'var(--text-secondary)' }}
                    >
                      {q}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Cadence archetypes */}
            {grammar.cadence_archetypes && (
              <div className="mb-3">
                <span className="text-[10px] uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>
                  Cadence Archetypes
                </span>
                <ul className="text-xs space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
                  {(Array.isArray(grammar.cadence_archetypes) ? grammar.cadence_archetypes : []).map((c: string, i: number) => (
                    <li key={i}>• {typeof c === 'string' ? c : JSON.stringify(c)}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Motion bias */}
            {grammar.motion_bias && (
              <div>
                <span className="text-[10px] uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>
                  Motion Bias
                </span>
                {Object.entries(grammar.motion_bias as Record<string, number>).map(([k, v]) => (
                  <div key={k} className="mb-1">
                    <div className="flex justify-between text-[10px] mb-0.5">
                      <span style={{ color: 'var(--text-secondary)' }}>{k}</span>
                      <span className="font-mono" style={{ color: 'var(--text-primary)' }}>{v}</span>
                    </div>
                    <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--surface-4)' }}>
                      <div
                        className="h-full rounded-full score-bar-animated"
                        style={{
                          width: `${(typeof v === 'number' ? v : 0) * 100}%`,
                          background: 'var(--accent-tertiary)',
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Collapsible research log */}
        {draft.research_log && (
          <div className="mb-4">
            <button
              onClick={() => setExpandResearchLog((v) => !v)}
              className="text-xs font-medium uppercase tracking-wider transition-colors"
              style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              {expandResearchLog ? '▾' : '▸'} Research Log
            </button>
            {expandResearchLog && (
              <div
                className="mt-2 rounded-xl p-4 card-animated"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
              >
                <pre
                  className="text-xs whitespace-pre-wrap font-mono"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {draft.research_log}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Collapsible critique trail */}
        {draft.critique_trail && draft.critique_trail.length > 0 && (
          <div className="mb-8">
            <button
              onClick={() => setExpandCritique((v) => !v)}
              className="text-xs font-medium uppercase tracking-wider transition-colors"
              style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              {expandCritique ? '▾' : '▸'} Critique Trail ({draft.critique_trail.length})
            </button>
            {expandCritique && (
              <div
                className="mt-2 rounded-xl p-4 card-animated"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
              >
                {draft.critique_trail.map((entry: any, i: number) => (
                  <div key={i} className="mb-3 last:mb-0">
                    <pre
                      className="text-xs whitespace-pre-wrap font-mono"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      {typeof entry === 'string' ? entry : JSON.stringify(entry, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-3">
          {!rejectMode && (
            <>
              <button
                onClick={handleApprove}
                className="px-5 py-2 rounded-lg font-medium text-sm transition-all"
                style={{ background: 'var(--accent-tertiary)', color: 'var(--surface-0)' }}
              >
                Approve
              </button>
              <button
                onClick={() => setRejectMode(true)}
                className="px-5 py-2 rounded-lg font-medium text-sm transition-all"
                style={{ background: 'var(--surface-3)', color: 'var(--text-primary)' }}
              >
                Reject
              </button>
            </>
          )}
          {rejectMode && (
            <div className="flex flex-col gap-2 w-full max-w-md">
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Reason for rejection (optional)"
                rows={2}
                className="w-full px-4 py-2.5 rounded-lg text-sm focus:outline-none transition-colors resize-none"
                style={{
                  background: 'var(--surface-1)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)',
                }}
              />
              <div className="flex gap-2">
                <button
                  onClick={handleReject}
                  className="px-5 py-2 rounded-lg font-medium text-sm transition-all"
                  style={{ background: 'var(--score-low)', color: 'white' }}
                >
                  Confirm Reject
                </button>
                <button
                  onClick={() => setRejectMode(false)}
                  className="px-5 py-2 rounded-lg font-medium text-sm transition-all"
                  style={{ background: 'var(--surface-3)', color: 'var(--text-primary)' }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Fallback: loading or no review draft yet
  return (
    <div className="min-h-screen flex items-center justify-center">
      <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading...</p>
    </div>
  );
}
