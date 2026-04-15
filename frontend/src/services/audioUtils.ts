/**
 * audioUtils.ts — Shared Tone.js utilities for both audio engines.
 */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ToneModule = typeof import("tone") & Record<string, any>

let Tone: ToneModule | null = null
let isInitialised = false

export type { ToneModule }

export async function ensureTone(): Promise<ToneModule> {
  if (!Tone) {
    try {
      Tone = (await import("tone")) as ToneModule
    } catch {
      throw new Error("Failed to load audio library. Your browser may not support Web Audio.")
    }
  }
  if (!isInitialised) {
    try {
      await Tone.start()
      isInitialised = true
    } catch {
      throw new Error("Audio context blocked. Click the page first to enable audio playback.")
    }
  }
  return Tone
}

export function resetTone(): void {
  isInitialised = false
  Tone = null
}

export function normalizePitch(pitch: string): string {
  return pitch.replace("-", "b")
}

export function normalizePitches(pitches: string[]): string[] {
  return pitches.map(normalizePitch)
}
