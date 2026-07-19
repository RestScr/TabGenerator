import { useEffect, useId, useState } from 'react'
import { audioCandidateUrl, generateTabFromPreparation, uploadAudioForPreparation } from '../api/uploadTabApi'
import type { AudioPreparation, AudioPreparationCandidate, ProcessingJob, UploadProgress } from '../model'
import './UploadTabModal.css'

type UploadTabModalProps = {
  isOpen: boolean
  onClose: () => void
  onTabReady: (tabId: string) => void
}

const initialProgress: UploadProgress = {
  stage: 'idle',
  progress: 0,
  message: '',
}

export function UploadTabModal({ isOpen, onClose, onTabReady }: UploadTabModalProps) {
  const fileInputId = useId()
  const [file, setFile] = useState<File | undefined>()
  const [tuning, setTuning] = useState('standard_e')
  const [separateSources, setSeparateSources] = useState(true)
  const [voiceMode, setVoiceMode] = useState<'lead' | 'rhythm' | 'guitar' | 'all'>('guitar')
  const [capo, setCapo] = useState(0)
  const [tempoBpm, setTempoBpm] = useState('')
  const [downbeatOffsetS, setDownbeatOffsetS] = useState(0)
  const [beatsPerMeasure, setBeatsPerMeasure] = useState(4)
  const [maxFret, setMaxFret] = useState(20)
  const [progress, setProgress] = useState<UploadProgress>(initialProgress)
  const [error, setError] = useState<string | undefined>()
  const [preparationJob, setPreparationJob] = useState<ProcessingJob | undefined>()
  const isBusy = progress.stage === 'uploading' || progress.stage === 'queued' || progress.stage === 'processing'

  useEffect(() => {
    if (!isOpen) {
      setFile(undefined)
      setTuning('standard_e')
      setSeparateSources(true)
      setVoiceMode('guitar')
      setCapo(0)
      setTempoBpm('')
      setDownbeatOffsetS(0)
      setBeatsPerMeasure(4)
      setMaxFret(20)
      setProgress(initialProgress)
      setError(undefined)
      setPreparationJob(undefined)
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!file || isBusy) return

    setError(undefined)
    try {
      const preparedJob = await uploadAudioForPreparation(file, tuning, separateSources, {
        voiceMode,
        capo,
        tempoBpm: tempoBpm === '' ? undefined : Number(tempoBpm),
        downbeatOffsetS,
        beatsPerMeasure,
        maxFret,
      }, setProgress)
      const generatedTabId = preparedJob.options.generated_tab_id
      if (typeof generatedTabId === 'string') {
        onTabReady(generatedTabId)
        onClose()
      } else {
        setProgress(initialProgress)
        setPreparationJob(preparedJob)
      }
    } catch (uploadError) {
      setProgress((current) => ({ ...current, stage: 'failed' }))
      setError(uploadError instanceof Error ? uploadError.message : 'Не удалось загрузить файл')
    }
  }

  return (
    <div className="upload-modal-backdrop" role="presentation" onMouseDown={() => !isBusy && onClose()}>
      <section
        className="upload-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-tab-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="upload-modal-heading">
          <div>
            <p className="upload-modal-eyebrow">Новая табулатура</p>
            <h2 id="upload-tab-title">Загрузить песню</h2>
          </div>
          <button className="upload-modal-close" type="button" onClick={onClose} disabled={isBusy} aria-label="Закрыть окно">×</button>
        </div>

        {preparationJob ? (
          <PreparedAudioCandidates job={preparationJob} onClose={onClose} onTabReady={onTabReady} />
        ) : (
        <form className="upload-modal-form" onSubmit={(event) => void handleSubmit(event)}>
          <label className="upload-file-field" htmlFor={fileInputId}>
            <span className="upload-file-icon" aria-hidden="true">↑</span>
            <span className="upload-file-copy">
              <strong>{file ? file.name : 'Выберите аудиофайл'}</strong>
              <small>{file ? `${Math.ceil(file.size / 1024 / 1024)} МБ` : 'MP3, WAV, FLAC, M4A или OGG, до 100 МБ'}</small>
            </span>
            <span className="upload-file-action">Выбрать</span>
            <input
              id={fileInputId}
              type="file"
              accept="audio/mpeg,audio/wav,audio/flac,audio/mp4,audio/ogg,.mp3,.wav,.flac,.m4a,.ogg"
              onChange={(event) => setFile(event.target.files?.[0])}
              disabled={isBusy}
            />
          </label>

          <label className="upload-tuning-field">
            <span>Строй</span>
            <select value={tuning} onChange={(event) => setTuning(event.target.value)} disabled={isBusy}>
              <option value="standard_e">Standard E: E A D G B E</option>
              <option value="c_sharp">Нижняя струна C#</option>
              <option value="drop_d">Drop D: D A D G B E</option>
            </select>
          </label>

          <div className="upload-rhythm-grid">
            <label className="upload-tuning-field">
              <span>Гитарная партия</span>
              <select value={voiceMode} onChange={(event) => setVoiceMode(event.target.value as typeof voiceMode)} disabled={isBusy}>
                <option value="lead">Мелодия / lead</option>
                <option value="rhythm">Нижняя / rhythm</option>
                <option value="guitar">Чистая электро-гитара</option>
                <option value="all">Все найденные ноты</option>
              </select>
            </label>
            <label className="upload-tuning-field">
              <span>Каподастр, лад</span>
              <input type="number" min="0" max="12" value={capo} onChange={(event) => setCapo(Number(event.target.value))} disabled={isBusy} />
            </label>
            <label className="upload-tuning-field">
              <span>Темп, BPM</span>
              <input type="number" min="30" max="300" placeholder="Авто" value={tempoBpm} onChange={(event) => setTempoBpm(event.target.value)} disabled={isBusy} />
            </label>
            <label className="upload-tuning-field">
              <span>Начало первого такта, сек.</span>
              <input type="number" min="0" max="60" step="0.01" value={downbeatOffsetS} onChange={(event) => setDownbeatOffsetS(Number(event.target.value))} disabled={isBusy} />
            </label>
            <label className="upload-tuning-field">
              <span>Размер</span>
              <select value={beatsPerMeasure} onChange={(event) => setBeatsPerMeasure(Number(event.target.value))} disabled={isBusy}>
                <option value={3}>3/4</option>
                <option value={4}>4/4</option>
                <option value={6}>6/4</option>
              </select>
            </label>
            <label className="upload-tuning-field">
              <span>Максимальный лад</span>
              <input type="number" min="5" max="24" value={maxFret} onChange={(event) => setMaxFret(Number(event.target.value))} disabled={isBusy} />
            </label>
          </div>

          <label className="upload-separation-field">
            <input
              type="checkbox"
              checked={separateSources}
              onChange={(event) => setSeparateSources(event.target.checked)}
              disabled={isBusy}
            />
            <span>
              <strong>Выделить гитару из микса</strong>
              <small>Нужно для обычной песни с вокалом, басом и ударными.</small>
            </span>
          </label>

          {isBusy && (
            <div className="upload-progress" aria-live="polite">
              <div className="upload-progress-line"><span style={{ width: `${Math.max(8, progress.progress)}%` }}></span></div>
              <p>{progress.message}</p>
              <b>{progress.progress}%</b>
            </div>
          )}

          {error && <p className="upload-error" role="alert">{error}</p>}

          <div className="upload-modal-actions">
            <button className="upload-cancel" type="button" onClick={onClose} disabled={isBusy}>Отмена</button>
            <button className="upload-submit" type="submit" disabled={!file || isBusy}>
              {isBusy ? 'Обрабатываем...' : 'Подготовить аудио'}
            </button>
          </div>
        </form>
        )}
      </section>
    </div>
  )
}

function PreparedAudioCandidates({
  job,
  onClose,
  onTabReady,
}: {
  job: ProcessingJob
  onClose: () => void
  onTabReady: (tabId: string) => void
}) {
  const preparation = job.options.audio_preparation as AudioPreparation | undefined
  const candidates = preparation?.candidates ?? []
  const selectedCandidate = candidates.find((candidate) => candidate.selected)
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationError, setGenerationError] = useState<string | undefined>()

  const handleGenerateTab = async () => {
    if (!selectedCandidate || isGenerating) return
    setGenerationError(undefined)
    setIsGenerating(true)
    try {
      const tab = await generateTabFromPreparation(job.id, selectedCandidate.id)
      onTabReady(tab.id)
      onClose()
    } catch (error) {
      setGenerationError(error instanceof Error ? error.message : 'Не удалось построить табулатуру')
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <div className="audio-candidates-panel">
      <div className="audio-candidates-heading">
        <p className="upload-modal-eyebrow">Этап 1 завершён</p>
        <h3>Кандидаты Demucs + ноты GAPS</h3>
        <p>{preparation?.message || 'Аудио подготовлено.'}</p>
      </div>
      <div className="audio-candidates-summary">
        <span>Модель: <b>{preparation?.model_name || 'Demucs'}</b></span>
        <span>Проходов: <b>{preparation?.passes || 2}</b></span>
        <span>Кандидатов: <b>{candidates.length}</b></span>
      </div>
      <div className="audio-candidates-list">
        {candidates.map((candidate) => (
          <article className="audio-candidate-card" key={candidate.id}>
            <div className="audio-candidate-copy">
              <strong>{candidate.label}</strong>
              <small>
                Проход {candidate.pass_index} · {candidate.sample_rate.toLocaleString('ru-RU')} Гц · {formatDuration(candidate.duration_seconds)}
              </small>
            </div>
            <audio controls preload="metadata" src={audioCandidateUrl(job.id, candidate.id)} />
            <CandidateNotes candidate={candidate} />
            <a
              className="audio-candidate-download"
              href={audioCandidateUrl(job.id, candidate.id)}
              download={candidate.filename}
            >
              Скачать WAV
            </a>
          </article>
        ))}
      </div>
      {candidates.length === 0 && <p className="audio-candidates-empty">Кандидаты не были созданы.</p>}
      <p className="audio-candidates-next">
        Каждый WAV отдельно обработан GAPS. Лучший кандидат отмечен и будет передан следующему этапу: построение табулатуры.
      </p>
      {generationError && <p className="upload-error" role="alert">{generationError}</p>}
      <button
        className="upload-submit audio-candidates-generate"
        type="button"
        disabled={!selectedCandidate || isGenerating}
        onClick={() => void handleGenerateTab()}
      >
        {isGenerating ? 'Строим табулатуру...' : 'Создать таб из выбранного GAPS MIDI'}
      </button>
    </div>
  )
}

function CandidateNotes({ candidate }: { candidate: AudioPreparationCandidate }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const notes = candidate.notes ?? []
  const visibleNotes = isExpanded ? notes : notes.slice(0, 160)

  return (
    <div className="audio-candidate-notes">
      <div className="audio-candidate-notes-heading">
        <span>Ноты GAPS</span>
        <b>{candidate.note_count}</b>
        {candidate.selected && <em>лучший кандидат</em>}
      </div>
      {candidate.gaps_error ? (
        <p className="audio-candidate-notes-error">GAPS: {candidate.gaps_error}</p>
      ) : notes.length === 0 ? (
        <p className="audio-candidate-notes-empty">GAPS не нашёл пригодных нот.</p>
      ) : (
        <>
          <div
            className={`audio-note-sequence${isExpanded ? ' is-expanded' : ''}`}
            aria-label={`Ноты кандидата ${candidate.label}`}
          >
            {visibleNotes.map((note) => (
              <span className="audio-note-chip" key={note.id} title={`${note.start_seconds.toFixed(2)} с · ${note.duration_seconds.toFixed(2)} с`}>
                {note.name}
              </span>
            ))}
          </div>
          {notes.length > 160 && (
            <button className="audio-notes-toggle" type="button" onClick={() => setIsExpanded((current) => !current)}>
              {isExpanded ? 'Свернуть ноты' : `Показать все ноты (+${notes.length - 160})`}
            </button>
          )}
        </>
      )}
    </div>
  )
}

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60).toString().padStart(2, '0')
  return `${minutes}:${remainingSeconds}`
}
