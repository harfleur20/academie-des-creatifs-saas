import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useRef, useState } from 'react'
import {
  CheckCircle2,
  Clock3,
  LockKeyhole,
  RotateCcw,
  Timer,
  X,
} from 'lucide-react'
import {
  ApiError,
  listStudentQuizzes,
  submitStudentQuizAttempt,
  type QuizAttempt,
  type StudentQuiz,
  type StudentQuizQuestion,
} from '../lib/api'
import { QuizAttemptReview } from '../components/QuizAttemptReview'

type Review = { title: string; questions: StudentQuizQuestion[]; attempt: QuizAttempt; passPct: number }

function timerStorageKey(quiz: StudentQuiz) {
  return `student_quiz_started_${quiz.id}_${quiz.attempts.length + 1}`
}

function quizStatus(quiz: StudentQuiz) {
  if (quiz.passed) {
    return <span className="dsh-badge dsh-badge--green"><CheckCircle2 size={12} /> Réussi · {quiz.best_score_pct}%</span>
  }
  if (quiz.work_closed) {
    return <span className="dsh-badge dsh-badge--gray"><LockKeyhole size={12} /> Session terminée</span>
  }
  if (quiz.pdf_reading_locked) {
    return <span className="dsh-badge dsh-badge--gray"><LockKeyhole size={12} /> Lecture PDF requise</span>
  }
  if (quiz.is_locked) {
    return <span className="dsh-badge dsh-badge--gray"><LockKeyhole size={12} /> À venir</span>
  }
  if (quiz.next_attempt_available_at && new Date(quiz.next_attempt_available_at).getTime() > Date.now()) {
    return <span className="dsh-badge dsh-badge--yellow"><Clock3 size={12} /> Réessai en attente</span>
  }
  if (quiz.best_score_pct !== null) {
    return <span className="dsh-badge dsh-badge--orange"><RotateCcw size={12} /> À refaire · {quiz.best_score_pct}%</span>
  }
  return <span className="dsh-badge dsh-badge--blue"><Clock3 size={12} /> À faire</span>
}

export function StudentQuizzesPage() {
  const [items, setItems] = useState<StudentQuiz[]>([])
  const [active, setActive] = useState<StudentQuiz | null>(null)
  const [result, setResult] = useState<StudentQuiz | null>(null)
  const [review, setReview] = useState<Review | null>(null)
  // Options ticked per question: one for a single-answer question, several for a multiple-answer one.
  const [answers, setAnswers] = useState<Record<number, number[]>>({})
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const timerStartRef = useRef<number | null>(null)
  const autoSubmittedRef = useRef(false)

  useEffect(() => {
    listStudentQuizzes()
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  useEffect(() => {
    if (items.length && window.location.hash.startsWith('#quiz-')) {
      document.getElementById(window.location.hash.slice(1))?.scrollIntoView({ block: 'center' })
    }
  }, [items])

  function startClock(quiz: StudentQuiz) {
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = null

    if (!quiz.duration_minutes) {
      timerStartRef.current = null
      setSecondsLeft(null)
      return
    }

    const durationSeconds = quiz.duration_minutes * 60
    const key = timerStorageKey(quiz)
    const stored = Number(window.localStorage.getItem(key))
    const startedAt = Number.isFinite(stored) && stored > 0 ? stored : Date.now()
    if (!(Number.isFinite(stored) && stored > 0)) {
      window.localStorage.setItem(key, String(startedAt))
    }
    timerStartRef.current = startedAt

    const tick = () => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000)
      const remaining = Math.max(0, durationSeconds - elapsed)
      setSecondsLeft(remaining)
      if (remaining === 0 && timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }

    tick()
    timerRef.current = setInterval(tick, 1000)
  }

  function openQuiz(quiz: StudentQuiz) {
    setActive(quiz)
    setResult(null)
    setAnswers({})
    setError('')
    autoSubmittedRef.current = false
    startClock(quiz)
  }

  function closeQuiz() {
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = null
    timerStartRef.current = null
    setActive(null)
    setAnswers({})
    setSecondsLeft(null)
  }

  async function submit(autoSubmit = false) {
    if (!active) return
    if (!autoSubmit && active.questions.some((question) => !answers[question.id]?.length)) {
      setError('Répondez à toutes les questions avant de soumettre.')
      return
    }

    setWorking(true)
    setError('')
    try {
      const answerList = active.questions.map((question) => question.selection_mode === 'multiple'
        ? answers[question.id] ?? []
        : answers[question.id]?.[0] ?? -1)
      const updated = await submitStudentQuizAttempt(active.id, answerList)
      window.localStorage.removeItem(timerStorageKey(active))
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item))
      setResult(updated)
      const attempt = updated.attempts[updated.attempts.length - 1]
      // As on the mother site, the correction opens right after each attempt.
      if (attempt) setReview({ title: active.title, questions: active.questions, attempt, passPct: updated.pass_pct })
      closeQuiz()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Soumission impossible.')
    } finally {
      setWorking(false)
    }
  }

  useEffect(() => {
    if (
      secondsLeft === 0 &&
      active &&
      !working &&
      !autoSubmittedRef.current
    ) {
      autoSubmittedRef.current = true
      void submit(true)
    }
  }, [secondsLeft, active, working])

  function timerLabel() {
    if (secondsLeft === null) return null
    const minutes = Math.floor(secondsLeft / 60)
    const seconds = secondsLeft % 60
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }

  const timerTone = active?.duration_minutes && secondsLeft !== null
    ? secondsLeft <= 60
      ? ' quiz-timer--danger'
      : secondsLeft <= Math.max(120, active.duration_minutes * 60 * .2)
        ? ' quiz-timer--warning'
        : ''
    : ''
  const timerPct = active?.duration_minutes && secondsLeft !== null
    ? Math.max(0, Math.min(100, (secondsLeft / (active.duration_minutes * 60)) * 100))
    : 100

  return (
    <main className="app-page">
      <div className="dsh-page dsh-page--quizzes">
        <div className="dsh-page__header">
          <h1>Quiz & examens</h1>
          <p className="dsh-page__subtitle">
            Testez vos acquis, suivez vos tentatives et reprenez un quiz dès que votre prochain essai est disponible.
          </p>
        </div>

        {result && (
          <div className={`dsh-result-banner ${result.passed ? 'dsh-result-banner--success' : 'dsh-result-banner--fail'}`}>
            <div>
              <strong>{result.passed ? 'Quiz réussi' : 'Tentative enregistrée'}</strong>
              <p>
                Meilleur score : {result.best_score_pct ?? 0}% · seuil de réussite : {result.pass_pct}%.
                {!result.passed && result.attempts_remaining > 0 ? ` ${result.attempts_remaining} essai(s) restant(s).` : ''}
                {!result.passed && result.next_attempt_available_at
                  ? ` Vos 3 essais sont utilisés : un nouveau cycle de 3 essais s'ouvre le ${new Date(result.next_attempt_available_at).toLocaleString(activeSchoolLocale())}.`
                  : ''}
              </p>
            </div>
            <button className="dsh-icon-btn" type="button" onClick={() => setResult(null)} aria-label="Fermer"><X size={14} /></button>
          </div>
        )}

        {error && <div className="dsh-error">{error}</div>}

        {items.length === 0 ? (
          <div className="dsh-empty">
            <div><CheckCircle2 size={28} /><strong>Aucune évaluation disponible</strong><p>Les quiz activés par vos professeurs apparaîtront ici.</p></div>
          </div>
        ) : (
          <div className="dsh-list">
            {items.map((quiz) => (
              <article className="dsh-list-item" id={`quiz-${quiz.id}`} key={quiz.id}>
                <div className="dsh-list-item__main">
                  <strong>{quiz.title}</strong>
                  <span className="dsh-list-item__meta">
                    {quiz.assessment_type === 'exam' ? 'Examen' : 'Quiz'} · {quiz.formation_title} · {quiz.session_label} · Prof. {quiz.teacher_name || '-'}
                  </span>
                  <span className="dsh-list-item__meta">
                    <span className="dsh-quiz-duration-badge"><Timer size={11} /> {quiz.duration_minutes || '-'} min</span>
                    {' · '}Seuil {quiz.pass_pct}% · {quiz.attempts_remaining} essai(s) restant(s)
                    {quiz.pdf_reading_pct !== null ? ` · PDF ${quiz.pdf_reading_pct}% lu` : ''}
                  </span>
                  {quiz.is_locked && !quiz.pdf_reading_locked && quiz.available_at && (
                    <span className="dsh-list-item__meta">Disponible le {new Date(quiz.available_at).toLocaleString(activeSchoolLocale())}</span>
                  )}
                  {quiz.next_attempt_available_at && (
                    <span className="dsh-list-item__meta">Prochain essai : {new Date(quiz.next_attempt_available_at).toLocaleString(activeSchoolLocale())}</span>
                  )}
                </div>

                <div className="dsh-list-item__actions">
                  {quizStatus(quiz)}
                  {quiz.can_attempt && (
                    <button className="dsh-btn dsh-btn--primary dsh-btn--sm" type="button" onClick={() => openQuiz(quiz)}>
                      {quiz.attempts.length ? <><RotateCcw size={12} /> Réessayer</> : 'Commencer'}
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>

      {active && (
        <div className="dsh-modal-overlay">
          <div className="dsh-modal dsh-modal--large" onClick={(event) => event.stopPropagation()}>
            <div className="dsh-modal__header">
              <div>
                <h3>{active.title}</h3>
                <span className="dsh-list-item__meta">
                  {active.assessment_type === 'exam' ? 'Examen' : 'Quiz'} · tentative {active.attempts.length + 1}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                {secondsLeft !== null && (
                  <div className={`quiz-timer${timerTone}`}>
                    <Timer size={13} />
                    <span className="quiz-timer__display">{timerLabel()}</span>
                    <span className="quiz-timer__bar"><span className="quiz-timer__bar-fill" style={{ width: `${timerPct}%` }} /></span>
                  </div>
                )}
                <button className="dsh-icon-btn" type="button" disabled={working} onClick={closeQuiz} aria-label="Fermer"><X size={16} /></button>
              </div>
            </div>

            <p className="dsh-modal__meta">
              Répondez à toutes les questions. {active.duration_minutes ? 'Le temps continue même si vous fermez cette fenêtre.' : 'Ce quiz n’est pas chronométré.'}
            </p>

            <div className="dsh-quiz-questions">
              {active.questions.map((question, index) => (
                <article className="dsh-quiz-question" key={question.id}>
                  <p className="dsh-quiz-question__text"><strong>{index + 1}.</strong> {question.text}</p>
                  {(question.selection_mode === 'multiple' || (question.points ?? 1) !== 1) && <p className="dsh-quiz-question__hint">
                    {question.selection_mode === 'multiple' && 'Plusieurs réponses possibles.'}
                    {(question.points ?? 1) !== 1 && ` ${question.points} points.`}
                  </p>}
                  <div className="dsh-quiz-options">
                    {question.options.map((option, optionIndex) => {
                      const multiple = question.selection_mode === 'multiple'
                      const ticked = answers[question.id]?.includes(optionIndex) ?? false
                      return (
                        <label className={`dsh-quiz-option${ticked ? ' is-selected' : ''}`} key={optionIndex}>
                          <input
                            type={multiple ? 'checkbox' : 'radio'}
                            name={`student-q-${question.id}`}
                            checked={ticked}
                            onChange={() => setAnswers((current) => {
                              const picked = current[question.id] ?? []
                              const next = !multiple ? [optionIndex]
                                : picked.includes(optionIndex) ? picked.filter((value) => value !== optionIndex) : [...picked, optionIndex]
                              return { ...current, [question.id]: next }
                            })}
                          />
                          <span>{option}</span>
                        </label>
                      )
                    })}
                  </div>
                </article>
              ))}
            </div>

            {secondsLeft === 0 && <div className="dsh-error" style={{ margin: '0 18px 14px' }}>Temps écoulé - soumission automatique en cours…</div>}

            <div className="dsh-modal__footer">
              <button className="dsh-btn dsh-btn--ghost" type="button" disabled={working} onClick={closeQuiz}>Fermer</button>
              <button className="dsh-btn dsh-btn--primary" type="button" disabled={working || secondsLeft === 0} onClick={() => void submit(false)}>
                {working ? 'Correction…' : 'Soumettre mes réponses'}
              </button>
            </div>
          </div>
        </div>
      )}

      {review && (
        <div className="dsh-modal-overlay" onClick={() => setReview(null)}>
          <div className="dsh-modal dsh-modal--large" onClick={(event) => event.stopPropagation()}>
            <div className="dsh-modal__header">
              <div>
                <h3>Correction · {review.title}</h3>
              </div>
              <button className="dsh-icon-btn" type="button" onClick={() => setReview(null)} aria-label="Fermer"><X size={16} /></button>
            </div>
            <QuizAttemptReview questions={review.questions} attempt={review.attempt} passPct={review.passPct} />
            <div className="dsh-modal__footer">
              <button className="dsh-btn dsh-btn--primary" type="button" onClick={() => setReview(null)}>Fermer la correction</button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
