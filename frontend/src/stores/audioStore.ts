import { create } from "zustand"

interface AudioState {
  playing: boolean
  paused: boolean
  tempo: number
  loop: boolean
  mutedTracks: { voicing: boolean; bass: boolean; melody: boolean }
  volume: number
  currentPosition: number
  setPlaying: (playing: boolean) => void
  setPaused: (paused: boolean) => void
  setTempo: (tempo: number) => void
  setLoop: (loop: boolean) => void
  toggleMute: (track: "voicing" | "bass" | "melody") => void
  setVolume: (volume: number) => void
  setCurrentPosition: (position: number) => void
  reset: () => void
}

export const useAudioStore = create<AudioState>((set) => ({
  playing: false,
  paused: false,
  tempo: 120,
  loop: true,
  mutedTracks: { voicing: false, bass: false, melody: false },
  volume: -6,
  currentPosition: 0,
  setPlaying: (playing) => set({ playing }),
  setPaused: (paused) => set({ paused }),
  setTempo: (tempo) => set({ tempo }),
  setLoop: (loop) => set({ loop }),
  toggleMute: (track) => set((state) => ({ mutedTracks: { ...state.mutedTracks, [track]: !state.mutedTracks[track] } })),
  setVolume: (volume) => set({ volume }),
  setCurrentPosition: (position) => set({ currentPosition: position }),
  reset: () => set({ playing: false, paused: false, tempo: 120, loop: true, mutedTracks: { voicing: false, bass: false, melody: false }, volume: -6, currentPosition: 0 }),
}))
