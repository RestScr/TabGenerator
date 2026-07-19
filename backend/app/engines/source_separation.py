"""Optional Demucs preprocessing for full-song audio uploads."""

from __future__ import annotations

import importlib.util
import logging
import re
import time
from functools import lru_cache
from pathlib import Path

import numpy as np


logger = logging.getLogger(__name__)


class SourceSeparationError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _get_demucs_model(model_name: str):
    """Load one Demucs model once per audio-processing process."""

    from demucs.pretrained import get_model

    logger.info("Demucs: loading model %s", model_name)
    model = get_model(model_name)
    model.cpu()
    return model


def _load_stereo_audio(audio_path: Path, sample_rate: int) -> np.ndarray:
    import librosa

    waveform, _ = librosa.load(audio_path, sr=sample_rate, mono=False)
    if waveform.ndim == 1:
        waveform = waveform[None, :]
    if waveform.shape[0] == 1:
        waveform = np.repeat(waveform, 2, axis=0)
    elif waveform.shape[0] > 2:
        waveform = waveform[:2]
    return waveform.astype(np.float32, copy=False)


def _run_demucs(
    audio_path: Path,
    model_name: str,
) -> tuple[np.ndarray, int, np.ndarray, np.ndarray]:
    """Return (guitar stem, sample rate, original stereo, all stems)."""

    if importlib.util.find_spec("demucs") is None:
        raise SourceSeparationError(
            "Demucs is not installed in the configured audio-processing environment."
        )

    import torch
    from demucs.apply import apply_model

    model = _get_demucs_model(model_name)
    waveform = _load_stereo_audio(audio_path, model.samplerate)
    audio_tensor = torch.from_numpy(waveform).float().unsqueeze(0)
    with torch.no_grad():
        separated = apply_model(model, audio_tensor, device="cpu", progress=False)

    try:
        guitar_index = model.sources.index("guitar")
    except ValueError as error:
        raise SourceSeparationError(
            f"Demucs model {model_name!r} does not contain a dedicated guitar stem"
        ) from error

    source_waveforms = separated[0].cpu().numpy()
    return source_waveforms[guitar_index], model.samplerate, waveform, source_waveforms


def _write_wav(path: Path, waveform: np.ndarray, sample_rate: int) -> None:
    import soundfile

    path.parent.mkdir(parents=True, exist_ok=True)
    soundfile.write(path, waveform.T, sample_rate)


def _model_storage_name(model_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model_name).strip("._") or "demucs"


def _guitar_likeness(waveform: np.ndarray, sample_rate: int) -> float:
    """Score an audio candidate without assuming a particular song."""
    import librosa

    mono = waveform.mean(axis=0) if waveform.ndim == 2 else waveform
    if mono.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(mono))) + 1e-9)
    harmonic, percussive = librosa.effects.hpss(mono)
    harmonic_ratio = float(np.sqrt(np.mean(harmonic**2)) / rms)
    spectrum = np.abs(librosa.stft(mono, n_fft=2048, hop_length=512))
    frequencies = librosa.fft_frequencies(sr=sample_rate, n_fft=2048)
    guitar_band = (frequencies >= 70.0) & (frequencies <= 2500.0)
    band_ratio = float(spectrum[guitar_band].sum() / (spectrum.sum() + 1e-9))
    flatness = float(np.mean(librosa.feature.spectral_flatness(S=spectrum)))
    return harmonic_ratio * 0.6 + band_ratio * 0.25 + (1.0 - flatness) * 0.15


def isolate_guitar_candidates(
    audio_path: Path,
    output_dir: Path,
    model_name: str = "htdemucs_6s",
) -> list[Path]:
    """Create both useful Demucs guitar candidates.

    The legacy one-pass API keeps both candidates and lets downstream
    transcription decide which MIDI is better.  The audio-only preparation
    API is ``isolate_repeated_guitar_candidates`` below.
    """

    track_dir = output_dir / "separation" / _model_storage_name(model_name) / audio_path.stem
    direct_path = track_dir / "guitar_direct.wav"
    residual_path = track_dir / "guitar_residual.wav"
    if direct_path.is_file() and residual_path.is_file():
        return [direct_path, residual_path]

    started_at = time.monotonic()
    logger.info("Demucs: loading %s guitar-separation model for %s", model_name, audio_path.name)
    guitar_waveform, sample_rate, waveform, source_waveforms = _run_demucs(audio_path, model_name)

    duration_seconds = waveform.shape[-1] / sample_rate
    logger.info(
        "Demucs: audio decoded (channels=%s, sample_rate=%s, duration=%.1fs)",
        waveform.shape[0],
        sample_rate,
        duration_seconds,
    )
    logger.info("Demucs: first separation pass completed; building residual candidate")
    non_guitar_waveform = source_waveforms.sum(axis=0) - guitar_waveform
    residual_waveform = waveform - non_guitar_waveform
    track_dir.mkdir(parents=True, exist_ok=True)
    _write_wav(direct_path, guitar_waveform, sample_rate)
    _write_wav(residual_path, residual_waveform, sample_rate)
    logger.info(
        "Demucs: generated guitar candidates in %.1fs (candidates=%s)",
        time.monotonic() - started_at,
        ", ".join(path.name for path in (direct_path, residual_path)),
    )
    return [direct_path, residual_path]


def isolate_repeated_guitar_candidates(
    audio_path: Path,
    output_dir: Path,
    model_name: str = "htdemucs_6s",
    passes: int = 2,
) -> list[tuple[str, str, int, Path]]:
    """Run Demucs twice and retain every useful guitar audio candidate.

    Pass one separates the complete mix into a direct guitar stem and a
    reconstruction residual.  Pass two feeds only the direct guitar stem
    back into the same model and keeps its guitar output.  The result is a
    provenance-preserving list instead of an irreversible early selection.
    """

    if passes != 2:
        raise ValueError("The audio preparation stage currently supports exactly two Demucs passes")
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file was not found: {audio_path}")

    started_at = time.monotonic()
    track_dir = output_dir / "audio_preparation" / "demucs" / audio_path.stem
    pass_one_dir = track_dir / "pass_1"
    pass_two_dir = track_dir / "pass_2"
    direct_one = pass_one_dir / "guitar_direct.wav"
    residual_one = pass_one_dir / "guitar_residual.wav"
    direct_two = pass_two_dir / "guitar_refined.wav"

    if not (direct_one.is_file() and residual_one.is_file() and direct_two.is_file()):
        guitar_one, sample_rate, waveform_one, source_waveforms_one = _run_demucs(audio_path, model_name)
        non_guitar_one = source_waveforms_one.sum(axis=0) - guitar_one
        residual_one_waveform = waveform_one - non_guitar_one
        _write_wav(direct_one, guitar_one, sample_rate)
        _write_wav(residual_one, residual_one_waveform, sample_rate)

        guitar_two, sample_rate_two, _, _ = _run_demucs(direct_one, model_name)
        _write_wav(direct_two, guitar_two, sample_rate_two)

    logger.info(
        "Demucs: repeated separation completed in %.1fs (model=%s, passes=%s)",
        time.monotonic() - started_at,
        model_name,
        passes,
    )
    return [
        ("direct-pass-1", "Прямой гитарный stem, проход 1", 1, direct_one),
        ("residual-pass-1", "Остаточный гитарный кандидат, проход 1", 1, residual_one),
        ("refined-pass-2", "Очищенный direct stem, проход 2", 2, direct_two),
    ]


def isolate_guitar_track(audio_path: Path, output_dir: Path) -> Path:
    """Legacy adapter returning one candidate for the old pipeline.

    The candidate API is preferred when a processing pipeline is available.
    This adapter remains for callers of the original engine API.
    """

    candidates = isolate_guitar_candidates(audio_path, output_dir)
    selected_path = candidates[0].parent / "guitar.wav"
    return _select_guitar_candidate(candidates[0], candidates[1], selected_path)


def _select_guitar_candidate(direct_path: Path, residual_path: Path, selected_path: Path) -> Path:
    import librosa
    import soundfile

    candidates = []
    for path in (direct_path, residual_path):
        waveform, sample_rate = librosa.load(path, sr=None, mono=False)
        if waveform.ndim == 1:
            waveform = waveform[None, :]
        candidates.append((path, _guitar_likeness(waveform, sample_rate), waveform, sample_rate))

    best_path, best_score, best_waveform, best_sample_rate = max(candidates, key=lambda item: item[1])
    selected_path.parent.mkdir(parents=True, exist_ok=True)
    soundfile.write(selected_path, best_waveform.T, best_sample_rate)
    logger.info(
        "Demucs: guitar candidate scores direct=%.4f residual=%.4f selected=%s",
        candidates[0][1],
        candidates[1][1],
        best_path.name,
    )
    return selected_path
