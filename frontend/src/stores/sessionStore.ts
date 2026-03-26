import { create } from 'zustand';
import type { SessionSummary } from '../services/api';

interface SessionState {
  sessions: SessionSummary[];
  currentSession: SessionSummary | null;
  setSessions: (sessions: SessionSummary[]) => void;
  setCurrentSession: (session: SessionSummary | null) => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  sessions: [],
  currentSession: null,
  setSessions: (sessions) => set({ sessions }),
  setCurrentSession: (session) => set({ currentSession: session }),
}));
