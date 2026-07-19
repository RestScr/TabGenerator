import { apiConfig } from '../../../config/apiConfig'
import type { AudioPreparation, GeneratedTab, ProcessingJob, UploadProgress } from '../model'

type ApiErrorPayload = {
  detail?: string
}

export type TabGenerationSettings = {
  voiceMode: 'lead' | 'rhythm' | 'guitar' | 'all'
  capo: number
  tempoBpm?: number
  downbeatOffsetS: number
  beatsPerMeasure: number
  maxFret: number
}

function apiUrl(path: string): string {
  return `${apiConfig.baseUrl}${path}`
}

export function audioCandidateUrl(jobId: string, candidateId: string): string {
  return apiUrl(`/jobs/${encodeURIComponent(jobId)}/audio-preparation/${encodeURIComponent(candidateId)}`)
}

export async function generateTabFromPreparation(jobId: string, candidateId?: string): Promise<GeneratedTab> {
  const query = candidateId ? `?candidate_id=${encodeURIComponent(candidateId)}` : ''
  const response = await fetch(
    apiUrl(`/jobs/${encodeURIComponent(jobId)}/audio-preparation/tab${query}`),
    { method: 'POST' },
  )
  if (!response.ok) throw new Error(await getErrorMessage(response))
  return response.json() as Promise<GeneratedTab>
}

async function getErrorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json() as ApiErrorPayload
    if (payload.detail) return payload.detail
  } catch {
    // The API can return an empty non-JSON response when it is unavailable.
  }

  return `Ошибка сервера (${response.status})`
}

async function getProcessingJob(jobId: string): Promise<ProcessingJob> {
  const response = await fetch(apiUrl(`/jobs/${encodeURIComponent(jobId)}`))
  if (!response.ok) throw new Error(await getErrorMessage(response))
  return response.json() as Promise<ProcessingJob>
}

async function getAudioPreparation(jobId: string): Promise<AudioPreparation> {
  const response = await fetch(apiUrl(`/jobs/${encodeURIComponent(jobId)}/audio-preparation`))
  if (!response.ok) throw new Error(await getErrorMessage(response))
  return response.json() as Promise<AudioPreparation>
}

export async function uploadAudioForPreparation(
  file: File,
  tuning: string,
  separateSources: boolean,
  settings: TabGenerationSettings,
  onProgress: (progress: UploadProgress) => void,
): Promise<ProcessingJob> {
  onProgress({ stage: 'uploading', progress: 0, message: 'Загружаем аудиофайл...' })

  const formData = new FormData()
  formData.set('file', file)
  formData.set('instrument_type', 'lead_guitar')
  formData.set('voice_mode', settings.voiceMode)
  formData.set('capo', String(settings.capo))
  formData.set('tuning', tuning)
  formData.set('separate_sources', String(separateSources))
  if (settings.tempoBpm !== undefined) formData.set('tempo_bpm', String(settings.tempoBpm))
  formData.set('downbeat_offset_s', String(settings.downbeatOffsetS))
  formData.set('beats_per_measure', String(settings.beatsPerMeasure))
  formData.set('max_fret', String(settings.maxFret))

  const uploadResponse = await fetch(apiUrl('/jobs'), { method: 'POST', body: formData })
  if (!uploadResponse.ok) throw new Error(await getErrorMessage(uploadResponse))

  const createdJob = await uploadResponse.json() as ProcessingJob
  for (let attempt = 0; attempt < apiConfig.jobPollAttempts; attempt += 1) {
    const job = await getProcessingJob(createdJob.id)
    // Preparation state is file-backed for now, so do not wait for a status
    // update in processing_jobs. The database row stays read-only while
    // Demucs/GAPS is running.
    const preparation = await getAudioPreparation(createdJob.id)

    if (preparation.status === 'ready') {
      onProgress({ stage: 'processing', progress: 100, message: preparation.message || 'Кандидаты готовы.' })
      return {
        ...job,
        status: 'audio_prepared',
        progress: 100,
        options: {
          ...job.options,
          audio_preparation: preparation,
        },
      }
    }

    if (preparation.status === 'failed' || job.status === 'failed' || job.status === 'cancelled') {
      throw new Error(preparation.message || job.error_message || 'Не удалось подготовить аудио')
    }

    onProgress({
      stage: preparation.status === 'pending' ? 'queued' : 'processing',
      progress: preparation.progress ?? job.progress,
      message: preparation.message || 'Обрабатываем аудио через Demucs и GAPS...',
    })
    await wait(apiConfig.jobPollIntervalMs)
  }

  throw new Error('Подготовка аудио занимает слишком много времени. Попробуйте позже.')
}

async function getGeneratedTab(jobId: string): Promise<GeneratedTab> {
  const response = await fetch(apiUrl(`/jobs/${encodeURIComponent(jobId)}/tab`))
  if (!response.ok) throw new Error(await getErrorMessage(response))
  return response.json() as Promise<GeneratedTab>
}

function wait(delayMs: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, delayMs))
}

export async function uploadAudioForTab(
  file: File,
  tuning: string,
  separateSources: boolean,
  settings: TabGenerationSettings,
  onProgress: (progress: UploadProgress) => void,
): Promise<GeneratedTab> {
  onProgress({ stage: 'uploading', progress: 0, message: 'Загружаем аудиофайл...' })

  const formData = new FormData()
  formData.set('file', file)
  formData.set('instrument_type', 'lead_guitar')
  formData.set('voice_mode', settings.voiceMode)
  formData.set('capo', String(settings.capo))
  formData.set('tuning', tuning)
  formData.set('separate_sources', String(separateSources))
  if (settings.tempoBpm !== undefined) formData.set('tempo_bpm', String(settings.tempoBpm))
  formData.set('downbeat_offset_s', String(settings.downbeatOffsetS))
  formData.set('beats_per_measure', String(settings.beatsPerMeasure))
  formData.set('max_fret', String(settings.maxFret))

  const uploadResponse = await fetch(apiUrl('/jobs'), {
    method: 'POST',
    body: formData,
  })
  if (!uploadResponse.ok) throw new Error(await getErrorMessage(uploadResponse))

  const createdJob = await uploadResponse.json() as ProcessingJob

  for (let attempt = 0; attempt < apiConfig.jobPollAttempts; attempt += 1) {
    const job = await getProcessingJob(createdJob.id)

    if (job.status === 'completed') {
      onProgress({ stage: 'processing', progress: 100, message: 'Табулатура готова.' })
      return getGeneratedTab(job.id)
    }

    if (job.status === 'failed' || job.status === 'cancelled') {
      throw new Error(job.error_message || 'Не удалось создать табулатуру')
    }

    onProgress({
      stage: job.status === 'queued' ? 'queued' : 'processing',
      progress: job.progress,
      message: job.status === 'queued' ? 'Файл в очереди на обработку...' : 'Распознаём ноты и строим табулатуру...',
    })
    await wait(apiConfig.jobPollIntervalMs)
  }

  throw new Error('Обработка занимает слишком много времени. Попробуйте позже.')
}
