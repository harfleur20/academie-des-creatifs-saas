import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Minus, Plus } from 'lucide-react'
import {
  fetchLessonPdf, getLessonPdfProgress, listStudentQuizzes, reportLessonPdfPage, submitStudentQuizAttempt,
  type LearningLesson, type PdfLessonProgress, type QuizAttempt, type StudentQuiz, type StudentQuizQuestion,
} from '../lib/api'
import { QuizAttemptReview } from './QuizAttemptReview'

const PDFJS_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/5.4.149/pdf.min.mjs'
const PDFJS_WORKER = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/5.4.149/pdf.worker.min.mjs'

type PdfPage = {
  getViewport: (options: { scale: number }) => { width: number; height: number }
  render: (options: { canvas: HTMLCanvasElement; canvasContext: CanvasRenderingContext2D; viewport: { width: number; height: number } }) => { promise: Promise<void>; cancel: () => void }
}
type PdfDocument = { numPages: number; getPage: (page: number) => Promise<PdfPage>; destroy: () => Promise<void> }
type PdfJs = {
  GlobalWorkerOptions: { workerSrc: string }
  getDocument: (options: { data: Uint8Array }) => { promise: Promise<PdfDocument> }
}

export function PdfLessonReader({ lesson, onCompleted }: { lesson: LearningLesson; onCompleted?: () => void }) {
  const canvas = useRef<HTMLCanvasElement | null>(null)
  const [document, setDocument] = useState<PdfDocument | null>(null)
  const [progress, setProgress] = useState<PdfLessonProgress | null>(null)
  const [page, setPage] = useState(1)
  const [zoom, setZoom] = useState(1)
  const [renderedPage, setRenderedPage] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [quiz, setQuiz] = useState<StudentQuiz | null>(null)
  const [answers, setAnswers] = useState<Record<number, number>>({})
  const [submitting, setSubmitting] = useState(false)
  const [quizError, setQuizError] = useState('')
  const [hasStarted, setHasStarted] = useState(false)
  const [review, setReview] = useState<{ questions: StudentQuizQuestion[]; attempt: QuizAttempt } | null>(null)
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null)
  const autoSubmitted = useRef(false)

  useEffect(() => {
    let alive = true
    let loaded: PdfDocument | null = null
    setDocument(null)
    setProgress(null)
    setPage(1)
    setError('')
    setLoading(true)
    void (async () => {
      try {
        const [state, blob] = await Promise.all([getLessonPdfProgress(lesson.id), fetchLessonPdf(lesson.id)])
        const pdfjs = await import(/* @vite-ignore */ PDFJS_URL) as unknown as PdfJs
        pdfjs.GlobalWorkerOptions.workerSrc = PDFJS_WORKER
        loaded = await pdfjs.getDocument({ data: new Uint8Array(await blob.arrayBuffer()) }).promise
        if (!alive) return
        if (loaded.numPages !== state.page_count) throw new Error('La version du PDF ne correspond plus au suivi de lecture.')
        setProgress(state)
        setDocument(loaded)
        setPage(Math.max(1, Math.min(state.last_page, state.page_count)))
      } catch (caught) {
        if (alive) setError(caught instanceof Error ? caught.message : 'Le PDF ne peut pas être ouvert.')
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => { alive = false; if (loaded) void loaded.destroy() }
  }, [lesson.id])

  useEffect(() => {
    if (!document || !canvas.current) return
    let alive = true
    let renderTask: ReturnType<PdfPage['render']> | null = null
    setRenderedPage(0)
    void (async () => {
      try {
        const pdfPage = await document.getPage(page)
        if (!alive || !canvas.current) return
        const viewport = pdfPage.getViewport({ scale: zoom })
        const element = canvas.current
        const context = element.getContext('2d')
        if (!context) throw new Error('Affichage du PDF indisponible.')
        const ratio = Math.min(window.devicePixelRatio || 1, 2)
        element.width = Math.ceil(viewport.width * ratio)
        element.height = Math.ceil(viewport.height * ratio)
        element.style.width = `${viewport.width}px`
        element.style.height = `${viewport.height}px`
        context.setTransform(ratio, 0, 0, ratio, 0, 0)
        renderTask = pdfPage.render({ canvas: element, canvasContext: context, viewport })
        await renderTask.promise
        if (alive) setRenderedPage(page)
      } catch (caught) {
        if (alive) setError(caught instanceof Error ? caught.message : 'Cette page ne peut pas être affichée.')
      }
    })()
    return () => { alive = false; renderTask?.cancel() }
  }, [document, page, zoom])

  useEffect(() => {
    if (!progress || renderedPage !== page || error) return
    let active = true
    let timer: ReturnType<typeof setTimeout> | null = null
    const schedule = () => {
      if (timer) clearTimeout(timer)
      if (!active || window.document.visibilityState !== 'visible') return
      void reportLessonPdfPage(lesson.id, page, 'open').then((updated) => {
        if (active) setProgress(updated)
      }).catch(() => {})
      timer = setTimeout(() => {
        if (!active || window.document.visibilityState !== 'visible') return
        void reportLessonPdfPage(lesson.id, page, 'confirm').then((updated) => {
          if (active) setProgress(updated)
        }).catch(() => {})
      }, 2500)
    }
    schedule()
    window.document.addEventListener('visibilitychange', schedule)
    return () => { active = false; if (timer) clearTimeout(timer); window.document.removeEventListener('visibilitychange', schedule) }
  }, [lesson.id, page, renderedPage, Boolean(error)])

  useEffect(() => {
    if (!progress?.quiz_unlocked || !lesson.quiz_id) return
    let alive = true
    void listStudentQuizzes().then((items) => {
      if (alive) setQuiz(items.find((item) => item.id === lesson.quiz_id) ?? null)
    }).catch((caught) => { if (alive) setQuizError(caught instanceof Error ? caught.message : 'Quiz indisponible.') })
    return () => { alive = false }
  }, [lesson.id, lesson.quiz_id, progress?.quiz_unlocked])

  useEffect(() => {
    if (!hasStarted || secondsLeft === null) return
    const timer = window.setInterval(() => setSecondsLeft((current) => current === null ? null : Math.max(0, current - 1)), 1000)
    return () => window.clearInterval(timer)
  }, [hasStarted, secondsLeft === null])

  useEffect(() => {
    if (hasStarted && secondsLeft === 0 && !autoSubmitted.current) {
      autoSubmitted.current = true
      void submitQuiz(true)
    }
  }, [secondsLeft, hasStarted])

  async function submitQuiz(auto = false) {
    if (!quiz || !quiz.can_attempt || submitting) return
    if (!auto && quiz.questions.some((question) => answers[question.id] === undefined)) {
      setQuizError('Répondez à toutes les questions.')
      return
    }
    setSubmitting(true)
    setQuizError('')
    try {
      const updated = await submitStudentQuizAttempt(quiz.id, quiz.questions.map((question) => answers[question.id] ?? -1))
      const attempt = updated.attempts[updated.attempts.length - 1]
      setReview(attempt ? { questions: quiz.questions, attempt } : null)
      setQuiz(updated)
      setAnswers({})
      setHasStarted(false)
      setSecondsLeft(null)
      const currentProgress = await getLessonPdfProgress(lesson.id)
      setProgress(currentProgress)
      if (currentProgress.is_completed) onCompleted?.()
    } catch (caught) {
      setQuizError(caught instanceof Error ? caught.message : 'Envoi du quiz impossible.')
    } finally {
      setSubmitting(false)
    }
  }

  const totalPages = progress?.page_count ?? 1
  return <section className="student-pdf-reader">
    <div className="student-pdf-toolbar">
      <button type="button" aria-label="Page précédente" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft size={17} /></button>
      <label>Page <input type="number" min={1} max={totalPages} value={page} onChange={(event) => setPage(Math.max(1, Math.min(totalPages, Number(event.target.value) || 1)))} /> / {totalPages}</label>
      <button type="button" aria-label="Page suivante" disabled={page >= totalPages} onClick={() => setPage(page + 1)}><ChevronRight size={17} /></button>
      <button type="button" aria-label="Réduire le zoom" onClick={() => setZoom((current) => Math.max(0.5, current - 0.25))}><Minus size={17} /></button>
      <span>{Math.round(zoom * 100)} %</span>
      <button type="button" aria-label="Augmenter le zoom" onClick={() => setZoom((current) => Math.min(2.5, current + 0.25))}><Plus size={17} /></button>
    </div>
    {loading && <p>Chargement du document…</p>}
    {error && <p role="alert">{error} La lecture ne sera pas comptabilisée tant que le document ne s’affiche pas.</p>}
    <div className="student-pdf-canvas"><canvas ref={canvas} aria-label={`Document PDF, page ${page} sur ${totalPages}`} /></div>
    {progress && <div className="student-pdf-progress">
      <strong>Lecture du document : {progress.viewed_pct} %</strong>
      <progress value={progress.viewed_pct} max={100} aria-label="Progression de lecture du PDF" />
      <p>{progress.viewed_pages.length} / {totalPages} pages consultées. Objectif : 80 %.</p>
      {!progress.quiz_unlocked && <p>Le quiz se débloquera après 80 % de lecture.</p>}
      {progress.quiz_unlocked && lesson.quiz_id && <div className="student-pdf-quiz">
        <h3>Quiz de validation</h3>
        {progress.is_completed && <p>Leçon validée.</p>}
        {quiz && <>
          <p>Seuil de réussite : {quiz.pass_pct} % · {quiz.attempts_remaining} essai(s) disponible(s).</p>
          {quiz.best_score_pct !== null && <p>Meilleur score : {quiz.best_score_pct} %.</p>}
          {quiz.next_attempt_available_at && <p>Prochain cycle le {new Date(quiz.next_attempt_available_at).toLocaleString('fr-FR')}.</p>}
          {review && !hasStarted && <QuizAttemptReview questions={review.questions} attempt={review.attempt} passPct={quiz.pass_pct} />}
          {quiz.can_attempt && !hasStarted && <button className="primary-button" type="button" onClick={() => {
            setReview(null)
            setHasStarted(true)
            setSecondsLeft(quiz.duration_minutes ? quiz.duration_minutes * 60 : null)
            setAnswers({})
            autoSubmitted.current = false
          }}>Commencer le quiz</button>}
          {hasStarted && secondsLeft !== null && <p>Temps restant : {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, '0')}</p>}
          {quiz.can_attempt && hasStarted && quiz.questions.map((question, index) => <fieldset key={question.id}>
            <legend>{index + 1}. {question.text}</legend>
            {question.options.map((option, optionIndex) => <label key={optionIndex}>
              <input type="radio" name={`pdf-q-${lesson.id}-${question.id}`} checked={answers[question.id] === optionIndex} onChange={() => setAnswers((current) => ({ ...current, [question.id]: optionIndex }))} /> {option}
            </label>)}
          </fieldset>)}
          {quiz.can_attempt && hasStarted && <button className="primary-button" type="button" disabled={submitting} onClick={() => void submitQuiz()}>{submitting ? 'Envoi…' : 'Valider mes réponses'}</button>}
        </>}
        {quizError && <p role="alert">{quizError}</p>}
        <Link to={`/app/student/quizzes#quiz-${lesson.quiz_id}`}>Voir aussi dans mes quiz</Link>
      </div>}
    </div>}
  </section>
}
