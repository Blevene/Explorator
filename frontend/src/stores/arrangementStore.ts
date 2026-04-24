import { create } from "zustand"
import type { ArrangementDetail, ArrangementSummary } from "../services/api"
import { toggleCuration as apiToggleCuration } from "../api/patterns"
import { toast } from "../lib/toast"

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
  toggleCuration: (arrangementId: string, nextState: boolean) => Promise<void>
  reset: () => void
}

export const useArrangementStore = create<ArrangementState>((set, get) => ({
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
  toggleCuration: async (arrangementId, nextState) => {
    const prevArrangements = get().arrangements
    const prevDetail = get().selectedDetail
    const optimisticTimestamp = nextState ? new Date().toISOString() : null
    set({
      arrangements: prevArrangements.map((a) =>
        a.id === arrangementId
          ? { ...a, is_curated: nextState, curated_at: optimisticTimestamp }
          : a,
      ),
      selectedDetail:
        prevDetail && prevDetail.id === arrangementId
          ? { ...prevDetail, is_curated: nextState, curated_at: optimisticTimestamp }
          : prevDetail,
    })
    try {
      const resp = await apiToggleCuration(arrangementId, nextState)
      set((state) => ({
        arrangements: state.arrangements.map((a) =>
          a.id === arrangementId
            ? { ...a, is_curated: resp.is_curated, curated_at: resp.curated_at }
            : a,
        ),
        selectedDetail:
          state.selectedDetail && state.selectedDetail.id === arrangementId
            ? { ...state.selectedDetail, is_curated: resp.is_curated, curated_at: resp.curated_at }
            : state.selectedDetail,
      }))
      toast.success(nextState ? "Curated" : "Removed from curated")
    } catch (err) {
      set({ arrangements: prevArrangements, selectedDetail: prevDetail })
      toast.error("Failed to update curation")
      throw err
    }
  },
  reset: () => set({ arrangements: [], selectedArrangementId: null, selectedDetail: null, loading: false, error: null }),
}))
