import { create } from "zustand";
import {
  createExportPackage,
  listExportPackages,
  type ExportPackage,
} from "../services/api";

interface ExportState {
  packages: ExportPackage[];
  isExporting: boolean;
  exportError: string | null;
  lastExportedPackage: ExportPackage | null;
  fetchPackages: (sessionId: string) => Promise<void>;
  createExport: (
    sessionId: string,
    candidateIds: string[],
    formats: string[],
  ) => Promise<void>;
  clearError: () => void;
  reset: () => void;
}

export const useExportStore = create<ExportState>((set) => ({
  packages: [],
  isExporting: false,
  exportError: null,
  lastExportedPackage: null,

  fetchPackages: async (sessionId) => {
    const packages = await listExportPackages(sessionId);
    set({ packages });
  },

  createExport: async (sessionId, candidateIds, formats) => {
    set({ isExporting: true, exportError: null });
    try {
      const pkg = await createExportPackage(sessionId, candidateIds, formats);
      set((state) => ({
        isExporting: false,
        lastExportedPackage: pkg,
        packages: [...state.packages, pkg],
      }));
    } catch (err) {
      set({
        isExporting: false,
        exportError: err instanceof Error ? err.message : "Export failed",
      });
    }
  },

  clearError: () => set({ exportError: null }),
  reset: () =>
    set({
      packages: [],
      isExporting: false,
      exportError: null,
      lastExportedPackage: null,
    }),
}));
