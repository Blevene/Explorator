import { create } from 'zustand';
import {
  approveDraft,
  getDraftDetail,
  listGenres,
  listPendingDrafts,
  rejectDraft,
  startGenreResearch,
  streamResearchProgress,
  type DraftSummary,
  type GenreResearchJob,
  type GenreSummary,
} from '../services/api';

interface GenreResearchState {
  // Genre library
  genres: GenreSummary[];
  pendingDrafts: DraftSummary[];

  // Active research
  activeJobId: string | null;
  activeJobStatus: string | null;
  progressDetail: string | null;
  errorMessage: string | null;

  // Review
  reviewDraft: GenreResearchJob | null;

  // SSE cleanup
  _eventSource: EventSource | null;

  // Actions
  fetchGenres: () => Promise<void>;
  fetchDrafts: () => Promise<void>;
  startResearch: (genreName: string, referenceArtists?: string[]) => Promise<void>;
  connectProgress: (jobId: string) => void;
  disconnectProgress: () => void;
  fetchDraftDetail: (jobId: string) => Promise<void>;
  doApproveDraft: (jobId: string) => Promise<void>;
  doRejectDraft: (jobId: string, reason?: string) => Promise<void>;
  reset: () => void;
}

export const useGenreResearchStore = create<GenreResearchState>((set, get) => ({
  genres: [],
  pendingDrafts: [],
  activeJobId: null,
  activeJobStatus: null,
  progressDetail: null,
  errorMessage: null,
  reviewDraft: null,
  _eventSource: null,

  fetchGenres: async () => {
    const data = await listGenres();
    set({ genres: data.items });
  },

  fetchDrafts: async () => {
    const data = await listPendingDrafts();
    set({ pendingDrafts: data.items });
  },

  startResearch: async (genreName, referenceArtists = []) => {
    const { job_id } = await startGenreResearch(genreName, referenceArtists);
    set({ activeJobId: job_id, activeJobStatus: 'researching', progressDetail: null, errorMessage: null });
    get().connectProgress(job_id);
  },

  connectProgress: (jobId) => {
    get().disconnectProgress();
    const es = streamResearchProgress(jobId);

    es.addEventListener('genre_research', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        set({
          activeJobStatus: data.status,
          progressDetail: data.detail,
        });

        if (data.status === 'pending_review') {
          es.close();
          set({ _eventSource: null });
          get().fetchDrafts();
        }
        if (data.status === 'failed') {
          es.close();
          set({ _eventSource: null, errorMessage: data.detail });
        }
      } catch {
        // Ignore parse errors
      }
    });

    es.onerror = () => {
      es.close();
      set({ _eventSource: null });
    };

    set({ _eventSource: es });
  },

  disconnectProgress: () => {
    const es = get()._eventSource;
    if (es) {
      es.close();
      set({ _eventSource: null });
    }
  },

  fetchDraftDetail: async (jobId) => {
    const draft = await getDraftDetail(jobId);
    set({ reviewDraft: draft });
  },

  doApproveDraft: async (jobId) => {
    await approveDraft(jobId);
    set({ reviewDraft: null });
    await get().fetchGenres();
    await get().fetchDrafts();
  },

  doRejectDraft: async (jobId, reason = '') => {
    await rejectDraft(jobId, reason);
    set({ reviewDraft: null });
    await get().fetchDrafts();
  },

  reset: () => {
    get().disconnectProgress();
    set({
      activeJobId: null,
      activeJobStatus: null,
      progressDetail: null,
      errorMessage: null,
      reviewDraft: null,
    });
  },
}));
