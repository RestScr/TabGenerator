# Backend Configuration

The real local configuration is stored in `backend/.env`. It is ignored by Git
and must never contain production credentials in a committed file.

Start from the safe template:

```bash
cp .env.example .env
```

`DEBUG` accepts `true`/`false` and also `debug`/`release`. Required MySQL values are `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`,
`MYSQL_USER`, and `MYSQL_PASSWORD`. `REDIS_URL` remains reserved for a future
queue integration.

Backend behavior that is not secret belongs in `app/core/settings.py`: upload
limits, allowed audio extensions, API prefix, local artifact folders, and CORS.

Run the API after installing `requirements-api.txt`:

```bash
uvicorn app.main:app --reload
```

The first endpoint is available at `GET /api/v1/health`.

## Database migrations

After MySQL is running and the values in `.env` are correct, create the schema:

```bash
./.venv/bin/alembic -c alembic.ini upgrade head
```

The migrations create `audio_assets`, `processing_jobs`, and `generated_tabs`.
Use MySQL 8.0+. Queue claiming will belong to the future processing worker;
the current API only owns the audio-preparation task.

## Processing jobs API

Create a job by uploading an audio file:

```bash
curl -F "file=@song.mp3;type=audio/mpeg" \
  -F "instrument_type=lead_guitar" \
  -F "tuning=standard_e" \
  -F "separate_sources=true" \
  -F "tempo_bpm=83" \
  -F "downbeat_offset_s=0" \
  -F "beats_per_measure=4" \
  -F "max_fret=20" \
  http://127.0.0.1:8002/api/v1/jobs
```

The API returns `202` and a job with the `queued` status. The API then starts
only the audio-preparation stage in a dedicated audio subprocess. It runs two
Demucs passes, sends all three resulting WAV candidates through GAPS, and
publishes a file-backed preparation state. The manifest under
`storage/artifacts/jobs/{job_id}/audio_preparation` contains the WAV metadata,
MIDI paths, note events, quality metrics, and the selected candidate.

`state.json` in the same directory contains progress and errors. Preparation
progress, notes, MIDI paths, and the final state are intentionally not written
to `processing_jobs` yet. Read them with `GET
/api/v1/jobs/{job_id}/audio-preparation`; the API combines `state.json` and
`manifest.json`. Each candidate audio can be streamed from
`GET /api/v1/jobs/{job_id}/audio-preparation/{candidate_id}`.

After reviewing the candidates, build a tablature from the selected GAPS MIDI
with `POST /api/v1/jobs/{job_id}/audio-preparation/tab`. Pass an optional
`candidate_id` query parameter to choose a particular candidate. The result is
written to the job artifact directory and is available from
`GET /api/v1/jobs/{job_id}/tab`; it is not inserted into `generated_tabs` yet.

The audio subprocess tries `AUDIO_PROCESSING_PYTHON`, then
`backend/.venv-audio/bin/python`, `backend/.venv-worker/bin/python`, and the
current Python interpreter. Install `requirements-audio.txt` in the selected
environment. The model and number of passes are configured by
`DEMUCS_MODEL_NAME` and `DEMUCS_PASSES`.

Supported guitar tunings are `standard_e`, `c_sharp`, and `drop_d`.
Set `separate_sources=false` only when the uploaded file is already an isolated
guitar track. Demucs downloads its model weights on the first full-mix job.
`tempo_bpm` can be omitted to detect it automatically; use `30..300` to lock it
manually. `downbeat_offset_s` sets the first bar's offset, `beats_per_measure`
sets the numerator of the time signature (`2..12`), and `max_fret` limits the
generated fingering to `5..24`.

## Generated tabs API

`GET /api/v1/tabs` returns summaries of completed tabs. `GET /api/v1/tabs/{tab_id}`
returns the complete ASCII tab and its artifact keys. To poll a particular upload,
call `GET /api/v1/jobs/{job_id}/tab`: it returns `409` until the job has produced
a result and `200` with the finished tab afterwards.

The API process does not import or load ML models. The audio subprocess is
deliberately isolated so the future queue worker can call the same
`prepare_audio_with_demucs` function without changing the API contract.
