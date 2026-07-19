"""CLI bridge used by the API and later by the processing worker."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.engines.audio_preparation import prepare_audio_with_demucs


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare guitar audio candidates with two Demucs passes")
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--job-output", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--model", default="htdemucs_6s")
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument("--tuning", default="standard_e")
    parser.add_argument("--max-fret", type=int, default=20)
    parser.add_argument("--capo", type=int, default=0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    prepare_audio_with_demucs(
        args.audio,
        args.job_output,
        args.artifact_root,
        model_name=args.model,
        passes=args.passes,
        tuning=args.tuning,
        max_fret=args.max_fret,
        capo=args.capo,
    )


if __name__ == "__main__":
    main()
