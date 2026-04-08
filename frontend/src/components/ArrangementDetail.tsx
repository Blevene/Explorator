import type { ArrangementDetail as ArrangementDetailType } from "../services/api"
import PianoRoll from "./PianoRoll"
import TransportBar from "./TransportBar"
import ScorePanel from "./ScorePanel"

interface ArrangementDetailProps {
  arrangement: ArrangementDetailType | null
  genre: string
}

export default function ArrangementDetail({ arrangement, genre }: ArrangementDetailProps) {
  if (!arrangement) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-950 text-slate-500 text-sm">
        Select an arrangement to view details
      </div>
    )
  }

  const scores = arrangement.scorecard?.scores ?? {}
  const weightedTotal = arrangement.scorecard?.weighted_total ?? arrangement.weighted_total

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-slate-950">
      <TransportBar arrangement={arrangement} genre={genre} />
      <div className="flex-1 overflow-auto">
        <PianoRoll arrangement={arrangement} genre={genre} />
      </div>
      <ScorePanel scores={scores} weightedTotal={weightedTotal} />
    </div>
  )
}
