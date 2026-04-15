import { describe, it, expect, beforeEach } from "vitest"
import { useComparisonAudioStore } from "../comparisonAudioStore"

function getState() {
  return useComparisonAudioStore.getState()
}

describe("comparisonAudioStore", () => {
  beforeEach(() => {
    getState().reset()
  })

  describe("transport state", () => {
    it("has correct defaults", () => {
      const s = getState()
      expect(s.playing).toBe(false)
      expect(s.paused).toBe(false)
      expect(s.tempo).toBe(120)
      expect(s.loop).toBe(true)
      expect(s.currentPosition).toBe(0)
    })

    it("setPlaying updates playing", () => {
      getState().setPlaying(true)
      expect(getState().playing).toBe(true)
    })

    it("setPaused updates paused", () => {
      getState().setPaused(true)
      expect(getState().paused).toBe(true)
    })

    it("setTempo updates tempo", () => {
      getState().setTempo(140)
      expect(getState().tempo).toBe(140)
    })

    it("setLoop updates loop", () => {
      getState().setLoop(false)
      expect(getState().loop).toBe(false)
    })

    it("setCurrentPosition updates currentPosition", () => {
      getState().setCurrentPosition(3.5)
      expect(getState().currentPosition).toBe(3.5)
    })
  })

  describe("mute", () => {
    it("toggleMute adds candidate to mutedLanes", () => {
      getState().toggleMute("candidate-1")
      expect(getState().mutedLanes["candidate-1"]).toBe(true)
    })

    it("toggleMute twice removes candidate from mutedLanes", () => {
      getState().toggleMute("candidate-1")
      getState().toggleMute("candidate-1")
      expect(getState().mutedLanes["candidate-1"]).toBe(false)
    })
  })

  describe("solo", () => {
    it("toggleSolo adds candidate to soloedLanes", () => {
      getState().toggleSolo("candidate-1")
      expect(getState().soloedLanes["candidate-1"]).toBe(true)
    })

    it("toggleSolo twice removes candidate from soloedLanes", () => {
      getState().toggleSolo("candidate-1")
      getState().toggleSolo("candidate-1")
      expect(getState().soloedLanes["candidate-1"]).toBe(false)
    })
  })

  describe("audibility logic", () => {
    function isAudible(id: string): boolean {
      const { mutedLanes, soloedLanes } = getState()
      const anySoloed = Object.values(soloedLanes).some(Boolean)
      return !mutedLanes[id] && (!anySoloed || !!soloedLanes[id])
    }

    it("all lanes audible when nothing muted or soloed", () => {
      expect(isAudible("a")).toBe(true)
      expect(isAudible("b")).toBe(true)
    })

    it("muted lane is not audible", () => {
      getState().toggleMute("a")
      expect(isAudible("a")).toBe(false)
      expect(isAudible("b")).toBe(true)
    })

    it("solo on one lane silences others", () => {
      getState().toggleSolo("a")
      expect(isAudible("a")).toBe(true)
      expect(isAudible("b")).toBe(false)
    })

    it("mute wins over solo", () => {
      getState().toggleSolo("a")
      getState().toggleMute("a")
      expect(isAudible("a")).toBe(false)
    })

    it("all lanes soloed means all audible", () => {
      getState().toggleSolo("a")
      getState().toggleSolo("b")
      getState().toggleSolo("c")
      expect(isAudible("a")).toBe(true)
      expect(isAudible("b")).toBe(true)
      expect(isAudible("c")).toBe(true)
    })

    it("two lanes soloed, third silent", () => {
      getState().toggleSolo("a")
      getState().toggleSolo("b")
      expect(isAudible("a")).toBe(true)
      expect(isAudible("b")).toBe(true)
      expect(isAudible("c")).toBe(false)
    })
  })

  describe("reset", () => {
    it("clears all state", () => {
      getState().setPlaying(true)
      getState().setTempo(180)
      getState().toggleMute("a")
      getState().toggleSolo("b")
      getState().setCurrentPosition(5.0)

      getState().reset()

      const s = getState()
      expect(s.playing).toBe(false)
      expect(s.tempo).toBe(120)
      expect(s.mutedLanes).toEqual({})
      expect(s.soloedLanes).toEqual({})
      expect(s.currentPosition).toBe(0)
    })
  })
})
