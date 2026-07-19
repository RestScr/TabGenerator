"""Map transcription pitches to playable guitar string and fret positions."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True)
class TranscriptionNote:
    start: float
    end: float | None
    pitch: int
    velocity: int


@dataclass(frozen=True)
class FretboardNote:
    start: float
    end: float | None
    string: int
    fret: int
    velocity: int
    assignment_confidence: float = 1.0


@dataclass(frozen=True)
class _ChordCandidate:
    notes: tuple[FretboardNote, ...]
    local_cost: float
    hand_position: float


class FretboardMapper:
    """Choose globally coherent guitar positions using beam-search dynamic programming."""

    ONSET_TOLERANCE_SECONDS = 0.08
    MAX_NOTES_PER_CHORD = 6
    MAX_CANDIDATES_PER_CHORD = 32

    @classmethod
    def map_notes(
        cls,
        notes: list[TranscriptionNote],
        string_pitches: list[int],
        max_fret: int,
        capo: int = 0,
    ) -> list[FretboardNote]:
        groups = cls._group_onsets(notes)
        candidates_by_group = [
            cls._chord_candidates(group, string_pitches, max_fret, capo)
            for group in groups
        ]
        candidates_by_group = [candidates for candidates in candidates_by_group if candidates]
        if not candidates_by_group:
            return []

        costs = [candidate.local_cost for candidate in candidates_by_group[0]]
        parents: list[list[int]] = [[-1] * len(costs)]

        for candidates in candidates_by_group[1:]:
            next_costs: list[float] = []
            next_parents: list[int] = []
            previous_candidates = candidates_by_group[len(parents) - 1]
            for candidate in candidates:
                best_index = 0
                best_cost = float("inf")
                for previous_index, previous_candidate in enumerate(previous_candidates):
                    transition = abs(candidate.hand_position - previous_candidate.hand_position)
                    cost = costs[previous_index] + candidate.local_cost + transition
                    if cost < best_cost:
                        best_cost = cost
                        best_index = previous_index
                next_costs.append(best_cost)
                next_parents.append(best_index)
            costs = next_costs
            parents.append(next_parents)

        candidate_index = min(range(len(costs)), key=costs.__getitem__)
        selected_groups: list[_ChordCandidate] = []
        for group_index in range(len(candidates_by_group) - 1, -1, -1):
            selected_groups.append(candidates_by_group[group_index][candidate_index])
            candidate_index = parents[group_index][candidate_index]
        selected_groups.reverse()
        return [note for group in selected_groups for note in group.notes]

    @classmethod
    def _group_onsets(cls, notes: list[TranscriptionNote]) -> list[list[TranscriptionNote]]:
        groups: list[list[TranscriptionNote]] = []
        for note in sorted(notes, key=lambda item: (item.start, -item.velocity, item.pitch)):
            if not groups or note.start - groups[-1][0].start > cls.ONSET_TOLERANCE_SECONDS:
                groups.append([note])
            else:
                groups[-1].append(note)
        return [
            sorted(group, key=lambda item: (-item.velocity, item.pitch))[: cls.MAX_NOTES_PER_CHORD]
            for group in groups
        ]

    @classmethod
    def _chord_candidates(
        cls,
        chord: list[TranscriptionNote],
        string_pitches: list[int],
        max_fret: int,
        capo: int = 0,
    ) -> list[_ChordCandidate]:
        states: list[tuple[float, tuple[FretboardNote, ...], frozenset[int]]] = [(0.0, (), frozenset())]
        for note in chord:
            positions = [
                (string, note.pitch - (open_pitch + capo))
                for string, open_pitch in enumerate(string_pitches)
                if 0 <= note.pitch - (open_pitch + capo) <= max_fret
            ]
            if not positions:
                continue

            next_states = []
            for cost, mapped_notes, used_strings in states:
                for string, fret in positions:
                    if string in used_strings:
                        continue
                    position_cost = fret * 0.15 + (0.8 if fret > 12 else 0.0)
                    mapped = FretboardNote(note.start, note.end, string, fret, note.velocity)
                    next_states.append((cost + position_cost, (*mapped_notes, mapped), used_strings | {string}))
            if not next_states:
                continue
            next_states.sort(key=lambda item: item[0])
            states = next_states[: cls.MAX_CANDIDATES_PER_CHORD]

        candidates = []
        for cost, mapped_notes, _ in states:
            if not mapped_notes:
                continue
            frets = [note.fret for note in mapped_notes if note.fret > 0]
            spread = max(frets) - min(frets) if len(frets) > 1 else 0
            hand_position = float(median(frets)) if frets else 0.0
            candidates.append(_ChordCandidate(mapped_notes, cost + spread * 0.7, hand_position))
        return candidates
