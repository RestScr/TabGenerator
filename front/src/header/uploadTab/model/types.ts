export type ProcessingJobStatus = 'queued' | 'processing' | 'audio_prepared' | 'completed' | 'failed' | 'cancelled'

export type AudioPreparationCandidate = {
  id: string
  label: string
  pass_index: number
  filename: string
  storage_key: string
  content_type: string
  size_bytes: number
  sample_rate: number
  channels: number
  duration_seconds: number
  midi_storage_key?: string
  midi_filename?: string
  note_count: number
  notes: AudioNote[]
  gaps_quality?: Record<string, number>
  gaps_error?: string
  selected?: boolean
}

export type AudioNote = {
  id: string
  pitch: number
  name: string
  start_seconds: number
  duration_seconds: number
  velocity: number
}

export type AudioPreparation = {
  status: 'pending' | 'processing' | 'ready' | 'skipped' | 'failed'
  progress: number
  message: string
  model_name?: string
  transcription_model?: string
  passes?: number
  tuning?: string
  max_fret?: number
  capo?: number
  manifest_storage_key?: string
  candidates: AudioPreparationCandidate[]
}

export type ProcessingJob = {
  id: string
  status: ProcessingJobStatus
  progress: number
  options: {
    audio_preparation?: AudioPreparation
    [key: string]: unknown
  }
  error_code: string | null
  error_message: string | null
}

export type GeneratedTab = {
  id: string
  processing_job_id: string
  title: string
  tempo_bpm: number
  ascii_tab: string
  ascii_tab_storage_key: string
  midi_storage_key: string | null
  note_events_storage_key: string | null
}

export type UploadStage = 'idle' | 'uploading' | 'queued' | 'processing' | 'failed'

export type UploadProgress = {
  stage: UploadStage
  progress: number
  message: string
}
