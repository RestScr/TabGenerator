import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { TabSection } from '../../tabSheet/model/types'

type ScheduledNode = {
  oscillator: OscillatorNode
  gain: GainNode
}

function formatTime(seconds: number): string {
  const roundedSeconds = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(roundedSeconds / 60)
  const remainingSeconds = roundedSeconds % 60
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

function midiToFrequency(midi: number): number {
  return 440 * 2 ** ((midi - 69) / 12)
}

export function useTabPlayback(section: TabSection) {
  const audioContextRef = useRef<AudioContext | null>(null)
  const animationFrameRef = useRef<number | undefined>(undefined)
  const scheduledNodesRef = useRef<ScheduledNode[]>([])
  const [isPlaying, setIsPlaying] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [activeNoteIds, setActiveNoteIds] = useState<Set<string>>(new Set())
  const [playedNoteIds, setPlayedNoteIds] = useState<Set<string>>(new Set())

  const beatDuration = 60 / section.tempoBpm
  const measureDuration = beatDuration * section.beatsPerMeasure
  const durationSeconds = section.measures.length * measureDuration
  const noteEvents = useMemo(
    () => section.measures.flatMap((measure, measureIndex) =>
      measure.notes.map((note) => ({
        ...note,
        time: measureIndex * measureDuration + note.position * measureDuration,
      })),
    ),
    [measureDuration, section.measures],
  )

  const clearScheduledAudio = useCallback(() => {
    scheduledNodesRef.current.forEach(({ gain, oscillator }) => {
      oscillator.onended = null
      try {
        oscillator.stop()
      } catch {
        // The oscillator can already be stopped after natural playback completion.
      }
      gain.disconnect()
      oscillator.disconnect()
    })
    scheduledNodesRef.current = []
  }, [])

  const stopPlayback = useCallback(() => {
    if (animationFrameRef.current !== undefined) {
      window.cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = undefined
    }
    clearScheduledAudio()
    setIsPlaying(false)
    setElapsedSeconds(0)
    setActiveNoteIds(new Set())
    setPlayedNoteIds(new Set())
  }, [clearScheduledAudio])

  const startPlayback = useCallback(async () => {
    clearScheduledAudio()
    const audioContext = audioContextRef.current ?? new AudioContext()
    audioContextRef.current = audioContext
    await audioContext.resume()

    const startAt = audioContext.currentTime + 0.08
    noteEvents.forEach((note) => {
      const stringMidi = section.stringMidi[note.stringIndex]
      if (stringMidi === undefined) return

      const noteStart = startAt + note.time
      const noteLength = Math.min(beatDuration * 1.4, Math.max(0.16, measureDuration - note.position * measureDuration))
      const eventLength = note.duration !== undefined && note.duration > 0
        ? note.duration
        : noteLength
      const oscillator = audioContext.createOscillator()
      const gain = audioContext.createGain()
      oscillator.type = 'triangle'
      oscillator.frequency.setValueAtTime(midiToFrequency(stringMidi + note.fret), noteStart)
      gain.gain.setValueAtTime(0.0001, noteStart)
      gain.gain.exponentialRampToValueAtTime(0.1, noteStart + 0.015)
      gain.gain.exponentialRampToValueAtTime(0.0001, noteStart + eventLength)
      oscillator.connect(gain)
      gain.connect(audioContext.destination)
      oscillator.start(noteStart)
      oscillator.stop(noteStart + eventLength + 0.02)
      scheduledNodesRef.current.push({ oscillator, gain })
    })

    const startedAt = performance.now() + 80
    setIsPlaying(true)
    setElapsedSeconds(0)
    setActiveNoteIds(new Set())
    setPlayedNoteIds(new Set())

    const tick = (now: number) => {
      const elapsed = Math.min(Math.max(0, (now - startedAt) / 1000), durationSeconds)
      setElapsedSeconds(elapsed)
      setPlayedNoteIds(new Set(noteEvents.filter((note) => note.time <= elapsed).map((note) => note.id)))
      setActiveNoteIds(new Set(
        noteEvents
          .filter((note) => elapsed >= note.time && elapsed < note.time + Math.min(note.duration || beatDuration * 0.7, 0.34))
          .map((note) => note.id),
      ))

      if (elapsed >= durationSeconds) {
        stopPlayback()
        return
      }

      animationFrameRef.current = window.requestAnimationFrame(tick)
    }

    animationFrameRef.current = window.requestAnimationFrame(tick)
  }, [beatDuration, clearScheduledAudio, durationSeconds, measureDuration, noteEvents, section.stringMidi, stopPlayback])

  const togglePlayback = useCallback(() => {
    if (isPlaying) {
      stopPlayback()
      return
    }
    void startPlayback()
  }, [isPlaying, startPlayback, stopPlayback])

  useEffect(() => stopPlayback, [stopPlayback])

  return {
    activeNoteIds,
    currentTime: formatTime(elapsedSeconds),
    duration: formatTime(durationSeconds),
    isPlaying,
    playedNoteIds,
    togglePlayback,
  }
}
