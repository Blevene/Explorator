import { create } from "zustand"

interface ComparisonAudioState {
  playing: boolean
  paused: boolean
  tempo: number
  loop: boolean
  currentPosition: number
  mutedLanes: Record<string, boolean>
  soloedLanes: Record<string, boolean>
  trackMutes: Record<string, { voicing: boolean; bass: boolean; melody: boolean }>
  setPlaying: (playing: boolean) => void
  setPaused: (paused: boolean) => void
  setTempo: (tempo: number) => void
  setLoop: (loop: boolean) => void
  setCurrentPosition: (position: number) => void
  toggleMute: (candidateId: string) => void
  toggleSolo: (candidateId: string) => void
  toggleTrackMute: (candidateId: string, track: "voicing" | "bass" | "melody") => void
  reset: () => void
}

const INITIAL_STATE = {
  playing: false,
  paused: false,
  tempo: 120,
  loop: true,
  currentPosition: 0,
  mutedLanes: {} as Record<string, boolean>,
  soloedLanes: {} as Record<string, boolean>,
  trackMutes: {} as Record<string, { voicing: boolean; bass: boolean; melody: boolean }>,
}

export const useComparisonAudioStore = create<ComparisonAudioState>((set) => ({
  ...INITIAL_STATE,
  setPlaying: (playing) => set({ playing }),
  setPaused: (paused) => set({ paused }),
  setTempo: (tempo) => set({ tempo }),
  setLoop: (loop) => set({ loop }),
  setCurrentPosition: (position) => set({ currentPosition: position }),
  toggleMute: (candidateId) =>
    set((state) => ({
      mutedLanes: { ...state.mutedLanes, [candidateId]: !state.mutedLanes[candidateId] },
    })),
  toggleSolo: (candidateId) =>
    set((state) => ({
      soloedLanes: { ...state.soloedLanes, [candidateId]: !state.soloedLanes[candidateId] },
    })),
  toggleTrackMute: (candidateId, track) =>
    set((state) => {
      const current = state.trackMutes[candidateId] ?? { voicing: false, bass: false, melody: false }
      return {
        trackMutes: {
          ...state.trackMutes,
          [candidateId]: { ...current, [track]: !current[track] },
        },
      }
    }),
  reset: () => set({ ...INITIAL_STATE, mutedLanes: {}, soloedLanes: {}, trackMutes: {} }),
}))
