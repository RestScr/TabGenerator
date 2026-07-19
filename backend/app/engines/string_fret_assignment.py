"""Probability-based string/fret assignment for transcribed guitar notes.

There is no pretrained string/fret checkpoint in the current worker
environment.  This module is therefore the model boundary we can run today:
it produces a probability distribution over playable positions using guitar
geometry and sequence context, then falls back to the legacy mapper when a
position cannot be generated.  A learned audio-conditioned scorer can replace
``_position_cost`` later without changing the worker contract.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from statistics import median

from app.engines.fretboard_mapper import FretboardMapper, FretboardNote, TranscriptionNote


@dataclass(frozen=True)
class _PositionState:
    cost: float
    notes: tuple[FretboardNote, ...]
    used_strings: frozenset[int]


@dataclass(frozen=True)
class _ChordHypothesis:
    notes: tuple[FretboardNote, ...]
    local_cost: float
    hand_position: float


class ProbabilisticStringFretMapper:
    """Select playable positions with local probabilities and global context."""

    MAX_CANDIDATES_PER_CHORD = 48
    TEMPERATURE = 0.55
    ONSET_TOLERANCE_SECONDS = 0.08
    MIN_CONFIDENCE = 0.10

    @classmethod
    def map_notes(
        cls,
        notes: list[TranscriptionNote],
        string_pitches: list[int],
        max_fret: int,
        capo: int = 0,
    ) -> list[FretboardNote]:
        groups = cls._group_onsets(notes)
        hypotheses_by_group = [
            cls._chord_hypotheses(group, string_pitches, max_fret, capo)
            for group in groups
        ]
        hypotheses_by_group = [hypotheses for hypotheses in hypotheses_by_group if hypotheses]
        if not hypotheses_by_group:
            return FretboardMapper.map_notes(notes, string_pitches, max_fret, capo)

        costs = [hypothesis.local_cost for hypothesis in hypotheses_by_group[0]]
        parents: list[list[int]] = [[-1] * len(costs)]

        for hypotheses in hypotheses_by_group[1:]:
            next_costs: list[float] = []
            next_parents: list[int] = []
            previous_hypotheses = hypotheses_by_group[len(parents) - 1]
            for hypothesis in hypotheses:
                best_parent = 0
                best_cost = float("inf")
                for previous_index, previous in enumerate(previous_hypotheses):
                    transition = cls._transition_cost(previous, hypothesis)
                    cost = costs[previous_index] + transition + hypothesis.local_cost
                    if cost < best_cost:
                        best_cost = cost
                        best_parent = previous_index
                next_costs.append(best_cost)
                next_parents.append(best_parent)
            costs = next_costs
            parents.append(next_parents)

        hypothesis_index = min(range(len(costs)), key=costs.__getitem__)
        selected: list[_ChordHypothesis] = []
        for group_index in range(len(hypotheses_by_group) - 1, -1, -1):
            selected.append(hypotheses_by_group[group_index][hypothesis_index])
            hypothesis_index = parents[group_index][hypothesis_index]
        selected.reverse()

        mapped: list[FretboardNote] = []
        selected_probabilities: list[float] = []
        for group_index, group in enumerate(selected):
            probabilities = cls._probabilities(hypotheses_by_group[group_index])
            # The selected hypothesis is already fixed by the global path.  A
            # local posterior remains useful to the UI as an uncertainty hint.
            probability = probabilities.get(group, 0.0)
            selected_probabilities.append(probability)
            mapped.extend(
                replace(note, assignment_confidence=probability)
                for note in group.notes
            )
        if selected_probabilities and min(selected_probabilities) < cls.MIN_CONFIDENCE:
            fallback = FretboardMapper.map_notes(notes, string_pitches, max_fret, capo)
            return [replace(note, assignment_confidence=0.5) for note in fallback]
        return [note for group in cls._sort_groups(mapped) for note in group]

    @classmethod
    def _sort_groups(cls, notes: list[FretboardNote]) -> list[list[FretboardNote]]:
        groups: list[list[FretboardNote]] = []
        for note in sorted(notes, key=lambda item: (item.start, item.string, item.fret)):
            if not groups or note.start - groups[-1][0].start > cls.ONSET_TOLERANCE_SECONDS:
                groups.append([note])
            else:
                groups[-1].append(note)
        return groups

    @classmethod
    def _group_onsets(cls, notes: list[TranscriptionNote]) -> list[list[TranscriptionNote]]:
        groups: list[list[TranscriptionNote]] = []
        for note in sorted(notes, key=lambda item: (item.start, -item.velocity, item.pitch)):
            if not groups or note.start - groups[-1][0].start > cls.ONSET_TOLERANCE_SECONDS:
                groups.append([note])
            else:
                groups[-1].append(note)
        return groups

    @classmethod
    def _chord_hypotheses(
        cls,
        chord: list[TranscriptionNote],
        string_pitches: list[int],
        max_fret: int,
        capo: int,
    ) -> list[_ChordHypothesis]:
        states: list[_PositionState] = [_PositionState(0.0, (), frozenset())]
        for note in chord:
            positions = [
                (string, note.pitch - (open_pitch + capo))
                for string, open_pitch in enumerate(string_pitches)
                if 0 <= note.pitch - (open_pitch + capo) <= max_fret
            ]
            if not positions:
                continue

            next_states: list[_PositionState] = []
            for state in states:
                for string, fret in positions:
                    if string in state.used_strings:
                        continue
                    mapped = FretboardNote(
                        note.start,
                        note.end,
                        string,
                        fret,
                        note.velocity,
                    )
                    next_states.append(
                        _PositionState(
                            state.cost + cls._position_cost(string, fret, string_pitches),
                            (*state.notes, mapped),
                            state.used_strings | {string},
                        )
                    )
            if next_states:
                next_states.sort(key=lambda state: state.cost)
                states = next_states[: cls.MAX_CANDIDATES_PER_CHORD]

        hypotheses = []
        for state in states:
            if not state.notes:
                continue
            frets = [note.fret for note in state.notes if note.fret > 0]
            hand_position = float(median(frets)) if frets else 0.0
            spread = max(frets) - min(frets) if len(frets) > 1 else 0
            hypotheses.append(
                _ChordHypothesis(
                    state.notes,
                    state.cost + spread * 0.35,
                    hand_position,
                )
            )
        return hypotheses

    @staticmethod
    def _position_cost(string: int, fret: int, string_pitches: list[int]) -> float:
        """Return a tunable prior cost for one playable position."""

        # Open strings and low positions are easier, while very high frets
        # are progressively less likely.  String distance from the middle of
        # the instrument is deliberately tiny; pitch alone must not force a
        # particular string.
        fret_cost = 0.035 * fret + (0.35 if fret > 12 else 0.0)
        open_string_bonus = -0.08 if fret == 0 else 0.0
        string_center = (len(string_pitches) - 1) / 2
        string_cost = abs(string - string_center) * 0.008
        return max(0.0, fret_cost + open_string_bonus + string_cost)

    @staticmethod
    def _transition_cost(previous: _ChordHypothesis, current: _ChordHypothesis) -> float:
        hand_shift = abs(current.hand_position - previous.hand_position)
        string_shift = abs(
            median([note.string for note in current.notes])
            - median([note.string for note in previous.notes])
        )
        return hand_shift * 0.28 + string_shift * 0.035

    @classmethod
    def _probabilities(cls, hypotheses: list[_ChordHypothesis]) -> dict[_ChordHypothesis, float]:
        if not hypotheses:
            return {}
        logits = [-hypothesis.local_cost / cls.TEMPERATURE for hypothesis in hypotheses]
        maximum = max(logits)
        weights = [math.exp(logit - maximum) for logit in logits]
        denominator = sum(weights) or 1.0
        return {
            hypothesis: weight / denominator
            for hypothesis, weight in zip(hypotheses, weights)
        }
