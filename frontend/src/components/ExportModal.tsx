import { useState } from "react";
import JSZip from "jszip";
import { useExportStore } from "../stores/exportStore";
import { getArtifactDownloadUrl } from "../services/api";
import type { ExportPackage } from "../services/api";

interface CandidateEntry {
  id: string;
  label: string;
  role: string;
  chords: string[];
}

interface Props {
  sessionId: string;
  candidates: CandidateEntry[];
  onClose: () => void;
}

const FORMAT_OPTIONS = [
  { id: "midi_combined", label: "Combined MIDI" },
  { id: "midi_separate", label: "Separate MIDI" },
  { id: "json", label: "JSON" },
];

const DEFAULT_FORMATS = new Set(["midi_combined", "json"]);
const FINALIST_ROLES = new Set(["best", "runner-up", "wildcard"]);

function roleBadgeStyle(role: string): React.CSSProperties {
  if (role === "best") return { background: "var(--accent-primary-dim)", color: "var(--accent-primary)" };
  if (role === "runner-up") return { background: "var(--accent-secondary-dim)", color: "var(--accent-secondary)" };
  if (role === "wildcard") return { background: "#6c9bef22", color: "#a78bfa" };
  return { background: "var(--surface-3)", color: "var(--text-secondary)" };
}

async function downloadArtifact(packageId: string, artifactId: string, filename: string) {
  const url = getArtifactDownloadUrl(packageId, artifactId);
  const res = await fetch(url);
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(blobUrl);
}

async function downloadAllAsZip(pkg: ExportPackage) {
  const zip = new JSZip();
  await Promise.all(
    pkg.artifacts.map(async (artifact) => {
      const url = getArtifactDownloadUrl(pkg.id, artifact.id);
      const res = await fetch(url);
      const blob = await res.blob();
      zip.file(artifact.filename, blob);
    })
  );
  const zipBlob = await zip.generateAsync({ type: "blob" });
  const url = URL.createObjectURL(zipBlob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `export-${pkg.id.slice(0, 8)}.zip`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ExportModal({ sessionId, candidates, onClose }: Props) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    new Set(candidates.filter((c) => FINALIST_ROLES.has(c.role)).map((c) => c.id))
  );
  const [selectedFormats, setSelectedFormats] = useState<Set<string>>(DEFAULT_FORMATS);
  const [zipping, setZipping] = useState(false);

  const { isExporting, exportError, lastExportedPackage, packages, createExport, clearError } =
    useExportStore();

  const toggleCandidate = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleFormat = (fmt: string) => {
    setSelectedFormats((prev) => {
      const next = new Set(prev);
      if (next.has(fmt)) next.delete(fmt);
      else next.add(fmt);
      return next;
    });
  };

  const handleExport = async () => {
    if (selectedIds.size === 0 || selectedFormats.size === 0) return;
    clearError();
    await createExport(sessionId, Array.from(selectedIds), Array.from(selectedFormats));
  };

  const handleDownloadAll = async (pkg: ExportPackage) => {
    setZipping(true);
    try {
      await downloadAllAsZip(pkg);
    } finally {
      setZipping(false);
    }
  };

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: "var(--overlay-backdrop)" }}
      onClick={onClose}
    >
      <div
        className="rounded-xl w-full max-w-lg max-h-[90vh] flex flex-col"
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border-default)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4"
          style={{ borderBottom: "1px solid var(--border-subtle)" }}
        >
          <h3 className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
            Export Arrangements
          </h3>
          <button
            onClick={onClose}
            className="text-lg leading-none transition-colors"
            style={{ color: "var(--text-muted)" }}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-5">
          {/* Candidates */}
          <section>
            <div className="text-xs font-medium uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
              Candidates
            </div>
            {candidates.length === 0 ? (
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                No candidates available.
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                {candidates.map((c) => (
                  <label
                    key={c.id}
                    className="flex items-start gap-3 cursor-pointer rounded-lg p-2 transition-colors"
                    style={{ background: selectedIds.has(c.id) ? "var(--surface-2)" : "transparent" }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(c.id)}
                      onChange={() => toggleCandidate(c.id)}
                      className="mt-0.5 accent-[var(--accent-primary)]"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                          {c.label}
                        </span>
                        {c.role && (
                          <span
                            className="text-xs px-1.5 py-0.5 rounded font-mono"
                            style={roleBadgeStyle(c.role)}
                          >
                            {c.role}
                          </span>
                        )}
                      </div>
                      <div className="text-xs font-mono mt-0.5 truncate" style={{ color: "var(--text-secondary)" }}>
                        {(c.chords ?? []).join(" → ")}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            )}
          </section>

          {/* Formats */}
          <section>
            <div className="text-xs font-medium uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
              Formats
            </div>
            <div className="flex flex-wrap gap-3">
              {FORMAT_OPTIONS.map((fmt) => (
                <label key={fmt.id} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedFormats.has(fmt.id)}
                    onChange={() => toggleFormat(fmt.id)}
                    className="accent-[var(--accent-primary)]"
                  />
                  <span className="text-sm" style={{ color: "var(--text-primary)" }}>
                    {fmt.label}
                  </span>
                </label>
              ))}
            </div>
          </section>

          {/* Export button + feedback */}
          <section className="flex flex-col gap-2">
            <button
              onClick={handleExport}
              disabled={isExporting || selectedIds.size === 0 || selectedFormats.size === 0}
              className="rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                background: "var(--accent-primary)",
                color: "var(--surface-0)",
              }}
            >
              {isExporting
                ? "Exporting..."
                : `Export ${selectedIds.size} candidate${selectedIds.size !== 1 ? "s" : ""}`}
            </button>

            {exportError && (
              <p className="text-xs rounded px-3 py-2" style={{ background: "#7f1d1d33", color: "#fca5a5", border: "1px solid #7f1d1d" }}>
                {exportError}
              </p>
            )}

            {lastExportedPackage && !isExporting && (
              <div className="rounded-lg p-3 flex flex-col gap-2" style={{ background: "var(--surface-2)", border: "1px solid var(--border-subtle)" }}>
                <div className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                  Export ready — {lastExportedPackage.artifacts.length} file{lastExportedPackage.artifacts.length !== 1 ? "s" : ""}
                </div>
                <div className="flex flex-col gap-1">
                  {(lastExportedPackage.artifacts ?? []).map((artifact) => (
                    <button
                      key={artifact.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        downloadArtifact(lastExportedPackage.id, artifact.id, artifact.filename);
                      }}
                      className="text-xs font-mono truncate transition-colors text-left cursor-pointer"
                      style={{ color: "var(--accent-secondary)" }}
                    >
                      {artifact.filename}
                    </button>
                  ))}
                </div>
                {(lastExportedPackage.artifacts ?? []).length > 1 && (
                  <button
                    onClick={() => handleDownloadAll(lastExportedPackage)}
                    disabled={zipping}
                    className="text-xs mt-1 rounded px-3 py-1.5 font-medium transition-colors disabled:opacity-50"
                    style={{ background: "var(--surface-3)", color: "var(--text-primary)", border: "1px solid var(--border-subtle)" }}
                  >
                    {zipping ? "Preparing zip..." : "Download All (.zip)"}
                  </button>
                )}
              </div>
            )}
          </section>

          {/* Export history */}
          {packages.length > 0 && (
            <details className="text-xs">
              <summary
                className="cursor-pointer font-medium select-none"
                style={{ color: "var(--text-secondary)" }}
              >
                Export history ({packages.length})
              </summary>
              <div className="flex flex-col gap-2 mt-2">
                {[...packages].reverse().filter(pkg => pkg?.id).map((pkg) => (
                  <div
                    key={pkg.id}
                    className="rounded-lg p-2"
                    style={{ background: "var(--surface-2)", border: "1px solid var(--border-subtle)" }}
                  >
                    <div className="font-mono" style={{ color: "var(--text-muted)" }}>
                      {(pkg.id ?? "").slice(0, 8)}… — {(pkg.artifacts ?? []).length} file{(pkg.artifacts ?? []).length !== 1 ? "s" : ""}
                    </div>
                    <div className="flex flex-wrap gap-2 mt-1">
                      {(pkg.artifacts ?? []).map((artifact) => (
                        <button
                          key={artifact.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            downloadArtifact(pkg.id, artifact.id, artifact.filename);
                          }}
                          className="font-mono truncate transition-colors cursor-pointer"
                          style={{ color: "var(--accent-secondary)" }}
                        >
                          {artifact.filename}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
