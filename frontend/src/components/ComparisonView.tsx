import { useEffect } from "react"
import type { ArrangementDetail } from "../services/api"
import { recordComparison } from "../services/api"
import * as audioEngine from "../services/audioEngine"
import * as comparisonAudioEngine from "../services/comparisonAudioEngine"
import { useAudioStore } from "../stores/audioStore"
import { useComparisonAudioStore } from "../stores/comparisonAudioStore"
import { useCandidateStore } from "../stores/candidateStore"
import { scoreColorVar } from "../utils/designTokens"
import PianoRoll from "./PianoRoll"
import ComparisonTransportBar from "./ComparisonTransportBar"
import LaneSidebar from "./LaneSidebar"

interface ComparisonViewProps {
  sessionId: string
  genre: string
  arrangements: Map<string, ArrangementDetail>
  candidateLabels: Record<string, string>
  onClose: () => void
}

const SCORE_DIMENSIONS = [
  "voice_leading",
  "playability",
  "register_density",
  "genre_fit",
  "emotional_fit",
  "theoretical_coherence",
  "cadence_quality",
  "novelty",
  "loopability",
]

function dimensionLabel(dim: string): string {
  return dim
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
}


export default function ComparisonView({
  sessionId,
  genre,
  arrangements,
  candidateLabels,
  onClose,
}: ComparisonViewProps) {
  const { selectedForComparison, clearComparison } = useCandidateStore()

  const candidateIds = selectedForComparison
  const comparedArrangements = candidateIds
    .map((id) => arrangements.get(id))
    .filter((a): a is ArrangementDetail => a !== undefined)

  // Fire-and-forget comparison recording
  useEffect(() => {
    if (comparedArrangements.length >= 2) {
      const labels: Record<string, string> = {}
      comparedArrangements.forEach((a, i) => {
        labels[a.id] = String.fromCharCode(65 + i) // A, B, C
      })
      recordComparison(
        sessionId,
        candidateIds,
        SCORE_DIMENSIONS,
        labels,
      )
    }
  }, [candidateIds.join(",")])

  // Read comparison audio state
  const { playing: compPlaying, currentPosition: compPosition, mutedLanes, soloedLanes } = useComparisonAudioStore()

  // On mount: stop single-arrangement playback and clear stale mute state
  useEffect(() => {
    audioEngine.stop()
    useAudioStore.getState().reset()
    return () => {
      comparisonAudioEngine.stop()
      useComparisonAudioStore.getState().reset()
    }
  }, [])

  // Sync lane mute state to engine when mute/solo toggles change
  useEffect(() => {
    const anySoloed = Object.values(soloedLanes).some(Boolean)
    for (const id of candidateIds) {
      const audible = !mutedLanes[id] && (!anySoloed || !!soloedLanes[id])
      comparisonAudioEngine.setLaneMute(id, !audible)
    }
  }, [mutedLanes, soloedLanes, candidateIds])

  // Compute audibility per lane (for visual dimming)
  const anySoloed = Object.values(soloedLanes).some(Boolean)
  function isLaneAudible(id: string): boolean {
    return !mutedLanes[id] && (!anySoloed || !!soloedLanes[id])
  }

  // Compute max bars across all arrangements for visual alignment
  const maxBars = Math.max(8, ...comparedArrangements.map((a) => {
    const allBars = [
      ...(a.voicing_plan?.voicing_events ?? []).map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
      ...(a.bass_line?.note_events ?? []).map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
    ]
    return allBars.length > 0 ? Math.max(...allBars) : 0
  }))

  if (comparedArrangements.length < 2) {
    return (
      <div className="p-4 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
        Select at least 2 candidates to compare.
      </div>
    )
  }

  // Collect all scores for leader highlighting
  const allScores: Record<string, Record<string, number>> = {}
  comparedArrangements.forEach((a) => {
    allScores[a.id] = a.scorecard?.scores ?? {}
  })

  const leaders: Record<string, string> = {}
  SCORE_DIMENSIONS.forEach((dim) => {
    let bestId = ""
    let bestScore = -1
    comparedArrangements.forEach((a) => {
      const s = allScores[a.id]?.[dim] ?? 0
      if (s > bestScore) {
        bestScore = s
        bestId = a.id
      }
    })
    if (bestId) leaders[dim] = bestId
  })

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
    >
      <ComparisonTransportBar
        arrangements={arrangements}
        genre={genre}
        onClose={() => { clearComparison(); onClose() }}
      />

      {/* Stacked piano rolls with lane sidebars */}
      <div style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        {comparedArrangements.map((a, i) => {
          const candidateId = candidateIds[i]
          const audible = isLaneAudible(candidateId)
          return (
            <div
              key={a.id}
              className="flex"
              style={{ borderBottom: i < comparedArrangements.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}
            >
              <LaneSidebar
                candidateId={candidateId}
                label={candidateLabels[candidateId] ?? String.fromCharCode(65 + i)}
                score={a.scorecard?.weighted_total ?? a.weighted_total ?? 0}
                audible={audible}
              />
              <div className="flex-1">
                <PianoRoll
                  arrangement={a}
                  genre={genre}
                  compact
                  showCursor
                  barWidth={90}
                  dimmed={!audible}
                  currentPosition={compPosition}
                  playing={compPlaying}
                  totalBars={maxBars}
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* Score comparison table */}
      <div className="p-4">
        <h3
          className="text-xs font-medium uppercase tracking-wider mb-2"
          style={{ color: 'var(--text-muted)' }}
        >
          Score Comparison
        </h3>
        <div className="space-y-1">
          {SCORE_DIMENSIONS.map((dim) => (
            <div key={dim} className="flex items-center text-xs">
              <span className="w-32 truncate" style={{ color: 'var(--text-muted)' }}>
                {dimensionLabel(dim)}
              </span>
              <div className="flex-1 flex gap-4">
                {comparedArrangements.map((a, i) => {
                  const score = allScores[a.id]?.[dim] ?? 0
                  const isLeader = leaders[dim] === a.id
                  return (
                    <span
                      key={a.id}
                      className="font-mono"
                      style={{ color: scoreColorVar(score), fontWeight: isLeader ? 700 : 400, opacity: isLeader ? 1 : 0.7 }}
                    >
                      {candidateLabels[candidateIds[i]] ?? String.fromCharCode(65 + i)}: {score.toFixed(1)}
                    </span>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
