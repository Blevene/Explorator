const NOTE_TO_SEMITONE: Record<string, number> = {
  C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11,
}

export function pitchToMidi(pitch: string): number {
  const normalized = pitch.replace("-", "b")
  const match = normalized.match(/^([A-G])(#|b)?(\d)$/)
  if (!match) return 60
  const [, note, accidental, octaveStr] = match
  const base = NOTE_TO_SEMITONE[note]
  const octave = parseInt(octaveStr, 10)
  let midi = (octave + 1) * 12 + base
  if (accidental === "#") midi += 1
  if (accidental === "b") midi -= 1
  return midi
}

export function midiToPitchLabel(midi: number): string {
  const NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
  const octave = Math.floor(midi / 12) - 1
  const note = NOTES[midi % 12]
  return `${note}${octave}`
}
