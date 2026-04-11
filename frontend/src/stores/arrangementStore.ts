import { create } from "zustand"
import type { ArrangementDetail, ArrangementSummary } from "../services/api"

interface ArrangementState {
  arrangements: ArrangementSummary[]
  selectedArrangementId: string | null
  selectedDetail: ArrangementDetail | null
  loading: boolean
  error: string | null
  setArrangements: (arrangements: ArrangementSummary[]) => void
  setSelectedArrangementId: (id: string | null) => void
  setSelectedDetail: (detail: ArrangementDetail | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

export const useArrangementStore = create<ArrangementState>((set) => ({
  arrangements: [],
  selectedArrangementId: null,
  selectedDetail: null,
  loading: false,
  error: null,
  setArrangements: (arrangements) => set({ arrangements }),
  setSelectedArrangementId: (id) => set({ selectedArrangementId: id }),
  setSelectedDetail: (detail) => set({ selectedDetail: detail }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  reset: () => set({ arrangements: [], selectedArrangementId: null, selectedDetail: null, loading: false, error: null }),
}))
