/**
 * audioPresets.ts — Genre synth presets shared by both audio engines.
 */

import type { ToneModule } from "./audioUtils"

export interface SynthOptions {
  oscillator?: { type: string }
  envelope?: { attack?: number; release?: number }
  volume?: number
}

export interface GenrePreset {
  voicing: SynthOptions
  bass: SynthOptions
}

export const GENRE_PRESETS: Record<string, GenrePreset> = {
  dream_pop: {
    voicing: { envelope: { attack: 0.3, release: 1.5 }, volume: -12 },
    bass: { oscillator: { type: "sine" }, envelope: { attack: 0.1, release: 1.0 } },
  },
  synthwave: {
    voicing: { oscillator: { type: "sawtooth" }, envelope: { attack: 0.01, release: 0.4 }, volume: -8 },
    bass: { oscillator: { type: "square" }, envelope: { attack: 0.005, release: 0.3 } },
  },
  cinematic: {
    voicing: { oscillator: { type: "triangle" }, envelope: { attack: 0.15, release: 2.0 }, volume: -10 },
    bass: { oscillator: { type: "sine" }, envelope: { attack: 0.2, release: 2.0 } },
  },
}

export function getPreset(genre: string): GenrePreset {
  const key = genre.toLowerCase().replace(/[\s-]/g, "_")
  return GENRE_PRESETS[key] ?? GENRE_PRESETS["dream_pop"]
}

export function deepMerge<T extends Record<string, unknown>>(base: T, override: Partial<T>): T {
  const result = { ...base }
  for (const k of Object.keys(override) as Array<keyof T>) {
    const bv = base[k]
    const ov = override[k]
    if (ov !== undefined) {
      if (bv !== null && typeof bv === "object" && !Array.isArray(bv) &&
          ov !== null && typeof ov === "object" && !Array.isArray(ov)) {
        result[k] = { ...(bv as object), ...(ov as object) } as T[keyof T]
      } else {
        result[k] = ov as T[keyof T]
      }
    }
  }
  return result
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function buildPolySynth(T: ToneModule, preset: SynthOptions): any {
  const defaults: Record<string, unknown> = {
    oscillator: { type: "triangle" },
    envelope: { attack: 0.1, decay: 0.2, sustain: 0.5, release: 0.8 },
  }
  const merged = deepMerge(defaults, preset as Record<string, unknown>)
  return new T.PolySynth(T.Synth, merged)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function buildMonoSynth(T: ToneModule, preset: SynthOptions): any {
  const defaults: Record<string, unknown> = {
    oscillator: { type: "sine" },
    envelope: { attack: 0.05, decay: 0.1, sustain: 0.8, release: 0.5 },
  }
  const merged = deepMerge(defaults, preset as Record<string, unknown>)
  return new T.MonoSynth(merged)
}
