import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, Clock3, Timer, XCircle } from 'lucide-react'
import {
  ApiError,
  listStudentQuizzes,
  submitStudentQuizAttempt,
  type StudentQuiz,
} from '../lib/api'

export function StudentQuizzesPage() {
  const [items, setItems] = useState<StudentQuiz[]>([])
  const [active, setActive] = useState<StudentQuiz | null>(null)
  const [answers, setAnswers] = useState<Record<number, number>>({})
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const autoSubmittedRef = useRef(false)

  useEffect(() => {
    listStudentQuizzes().then(setItems).catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  function openQuiz(quiz: StudentQuiz) {
    setActive(quiz)
    setAnswers({})
    setError('')
    autoSubmittedRef.current = false
    if (timerRef.current) clearInterval(timerRef.current)
    if (quiz.duration_minutes) {
      setSecondsLeft(quiz.duration_minutes * 60)
      timerRef.current = setInterval(() => {
        setSecondsLeft((value) => {
          if (value === null || value <= 1) {
            if (timerRef.current) clearInterval(timerRef.current)
            return 0
          }
          return value - 1
        })
      }, 1000)
    } else {
      setSecondsLeft(null)
    }
  }

  function closeQuiz() {
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = null
    setActive(null)
    setAnswers({})
    setSecondsLeft(null)
  }

  async function submit(autoSubmit = false) {
    if (!active) return
    if (
      !autoSubmit &&
      active.questions.some((question) => answers[question.id] === undefined)
    ) {
      setError('Répondez à toutes les questions.')
      return
    }
    setWorking(true)
    setError('')
    try {
      const answerList = active.questions.map(
        (question) => answers[question.id] ?? 0,
      )
      const updated = await submitStudentQuizAttempt(active.id, answerList)
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item))
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
    return String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0')
  }

  return (
    <main className="app-page academic-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Espace étudiant</span>
          <h1>Quiz & examens</h1>
          <p>Trois tentatives maximum par évaluation, avec un seuil défini par le professeur.</p>
        </div>
      </header>
      {error && <div className="form-error">{error}</div>}
      <section className="academic-card-list">
        {items.map((quiz) => (
          <article className="app-card student-quiz-card" key={quiz.id}>
            <div>
              <span className="section-label">{quiz.assessment_type === 'exam' ? 'Examen' : 'Quiz'}</span>
              <h2>{quiz.title}</h2>
              <small>{quiz.formation_title} · {quiz.session_label} · Prof. {quiz.teacher_name || '—'}</small>
            </div>
            <div className="student-quiz-stats">
              <span><Timer size={13}/>{quiz.duration_minutes || '—'} min</span>
              <span>Seuil {quiz.pass_pct}%</span>
              <span>{quiz.attempts_remaining} essai(s) restant(s)</span>
            </div>
            <div className="student-quiz-actions">
              {quiz.passed ? <span className="assignment-status reviewed"><CheckCircle2 size={13}/>Réussi · {quiz.best_score_pct}%</span> : quiz.best_score_pct !== null ? <span className="assignment-status late"><XCircle size={13}/>Meilleur score {quiz.best_score_pct}%</span> : <span className="assignment-status pending"><Clock3 size={13}/>À faire</span>}
              {quiz.can_attempt && <button className="primary-button compact-action" type="button" onClick={() => openQuiz(quiz)}>{quiz.attempts.length ? 'Réessayer' : 'Commencer'}</button>}
            </div>
          </article>
        ))}
        {items.length === 0 && <div className="app-card formation-empty"><CheckCircle2 size={26}/><strong>Aucune évaluation disponible</strong><p>Les quiz activés par vos professeurs apparaîtront ici.</p></div>}
      </section>

      {active && (
        <div className="assignment-modal-overlay">
          <div className="assignment-modal quiz-taking-modal">
            <header>
              <div><span className="section-label">{active.assessment_type}</span><h2>{active.title}</h2><p>Tentative {active.attempts.length + 1}</p></div>
              <div className="quiz-modal-head-actions">{secondsLeft !== null && <span className="quiz-countdown"><Timer size={14}/>{timerLabel()}</span>}<button type="button" onClick={closeQuiz}>×</button></div>
            </header>
            <div className="quiz-taking-questions">
              {active.questions.map((question, index) => (
                <article key={question.id}>
                  <strong>{index + 1}. {question.text}</strong>
                  <div>
                    {question.options.map((option, optionIndex) => (
                      <label className={answers[question.id] === optionIndex ? 'is-selected' : ''} key={optionIndex}>
                        <input type="radio" name={'student-q-' + question.id} checked={answers[question.id] === optionIndex} onChange={() => setAnswers((current) => ({ ...current, [question.id]: optionIndex }))}/>
                        {option}
                      </label>
                    ))}
                  </div>
                </article>
              ))}
            </div>
            {secondsLeft === 0 && (
              <div className="form-error">
                Temps écoulé — soumission automatique en cours…
              </div>
            )}
            <div className="quiz-modal-footer"><button className="secondary-button" type="button" onClick={closeQuiz}>Annuler</button><button className="primary-button" type="button" disabled={working || secondsLeft === 0} onClick={() => void submit(false)}>{working ? 'Correction…' : 'Soumettre'}</button></div>
          </div>
        </div>
      )}
    </main>
  )
}
