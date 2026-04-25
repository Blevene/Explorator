import { useCallback, useEffect, useRef, useState } from "react"
import type { ProvenanceEvent } from "../services/api"
import { getProvenance } from "../services/api"

interface SessionHistoryProps {
  sessionId: string
}

const ACTION_ICONS: Record<string, string> = {
  generate: "G",
  mutate: "M",
  feedback: "F",
  rank_and_select: "R",
  export: "E",
}

const ACTION_COLORS: Record<string, string> = {
  generate: "var(--action-generate)",
  mutate: "var(--action-mutate)",
  feedback: "var(--action-feedback)",
  rank_and_select: "var(--action-select)",
  export: "var(--action-export)",
}

function formatTime(timestamp: string): string {
  try {
    const d = new Date(timestamp)
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  } catch {
    return ""
  }
}

function describeEvent(event: ProvenanceEvent): string {
  const details = event.details as Record<string, unknown>
  switch (event.action) {
    case "generate":
      return `Generated ${details.candidate_count ?? "?"} candidates`
    case "mutate":
      return `Mutated ${(details.source_candidate_id as string)?.slice(-6) ?? "?"} \u2192 ${(details.result_candidate_id as string)?.slice(-6) ?? "?"}`
    case "feedback":
      return `Feedback loaded (${details.feedback_count ?? 0} items)`
    case "rank_and_select": {
      const roles = details.role_assignments as Record<string, string> | undefined
      const count = roles ? Object.keys(roles).length : (details.selected_count ?? "?")
      return `Ranked finalists (${count} selected)`
    }
    case "export":
      return `Exported candidates`
    default:
      return event.action
  }
}

export default function SessionHistory({ sessionId }: SessionHistoryProps) {
  const [events, setEvents] = useState<ProvenanceEvent[]>([])
  const [collapsed, setCollapsed] = useState(true)
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const fetchEvents = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getProvenance(sessionId)
      setEvents(data.events)
    } catch {
      // Silently fail — provenance is non-critical
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    fetchEvents()
  }, [fetchEvents])

  // Auto-scroll to newest
  useEffect(() => {
    if (!collapsed && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [events, collapsed])

  if (events.length === 0 && !loading) return null

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ border: '1px solid var(--border-default)' }}
    >
      <button
        onClick={() => {
          if (collapsed) fetchEvents()
          setCollapsed(!collapsed)
        }}
        aria-expanded={!collapsed}
        className="w-full flex items-center justify-between px-4 py-2 transition-colors bg-[var(--surface-2)] hover:bg-[var(--surface-3)] focus-visible:bg-[var(--surface-3)]"
      >
        <span
          className="text-xs font-medium uppercase tracking-wider"
          style={{ color: 'var(--text-secondary)' }}
        >
          Session History ({events.length})
        </span>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {collapsed ? "Show" : "Hide"}
        </span>
      </button>

      {!collapsed && (
        <div
          ref={scrollRef}
          className="max-h-64 overflow-y-auto p-3"
          style={{ background: 'var(--surface-1)' }}
        >
          {loading && events.length === 0 ? (
            <p className="text-xs text-center py-4" style={{ color: 'var(--text-muted)' }}>
              Loading...
            </p>
          ) : (
            <div className="space-y-2">
              {events.map((event, i) => (
                <div key={i} className="flex items-start gap-2">
                  {/* Timeline dot */}
                  <div className="flex flex-col items-center mt-0.5">
                    <div
                      className="w-5 h-5 rounded-full flex items-center justify-center text-white"
                      style={{
                        background: ACTION_COLORS[event.action] ?? 'var(--border-default)',
                        fontSize: "9px",
                        fontWeight: "bold",
                      }}
                    >
                      {ACTION_ICONS[event.action] ?? "?"}
                    </div>
                    {i < events.length - 1 && (
                      <div
                        className="w-px h-4 mt-0.5"
                        style={{ background: 'var(--border-subtle)' }}
                      />
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {describeEvent(event)}
                    </p>
                    <div className="flex gap-2" style={{ fontSize: "10px", color: 'var(--text-muted)' }}>
                      {event.round_number != null && (
                        <span>Round {event.round_number}</span>
                      )}
                      <span>{formatTime(event.timestamp)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
