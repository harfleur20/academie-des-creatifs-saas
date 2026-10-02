import { useEffect, useState, type FormEvent } from 'react'
import { BarChart3, CheckCircle2, Plus, Timer, Users, X } from 'lucide-react'
import {
  ApiError,
  createTeacherQuiz,
  getTeacherQuizResults,
  getTeacherWorkspace,
  listTeacherQuizzes,
  updateTeacherQuizStatus,
  type TeacherQuiz,
  type TeacherQuizResults,
  type TeacherWorkspace,
} from '../lib/api'

type DraftQuestion = {
  text: string
  options: [string, string, string, string]
  correct_index: number
}

const emptyQuestion = (): DraftQuestion => ({
  text: '',
  options: ['', '', '', ''],
  correct_index: 0,
})

export function TeacherQuizzesPage() {
  const [workspace, setWorkspace] = useState<TeacherWorkspace | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [items, setItems] = useState<TeacherQuiz[]>([])
  const [title, setTitle] = useState('')
  const [assessmentType, setAssessmentType] = useState<'quiz' | 'exam'>('quiz')
  const [duration, setDuration] = useState('30')
  const [questions, setQuestions] = useState<DraftQuestion[]>([emptyQuestion()])
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState<TeacherQuizResults | null>(null)

  useEffect(() => {
    getTeacherWorkspace().then((data) => {
      setWorkspace(data)
      setSessionId(data.sessions[0]?.session_id ?? null)
    }).catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [])

  async function refresh(id: number) {
    setItems(await listTeacherQuizzes(id))
  }

  useEffect(() => {
    if (sessionId) void refresh(sessionId).catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [sessionId])

  function changeQuestion(index: number, patch: Partial<DraftQuestion>) {
    setQuestions((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item))
  }

  function changeOption(questionIndex: number, optionIndex: number, value: string) {
    setQuestions((current) => current.map((item, itemIndex) => {
      if (itemIndex !== questionIndex) return item
      const next = [...item.options] as DraftQuestion['options']
      next[optionIndex] = value
      return { ...item, options: next }
    }))
  }

  async function create(event: FormEvent) {
    event.preventDefault()
    if (!sessionId) return
    const normalized = questions.map((question) => ({
      text: question.text.trim(),
      options: question.options.map((option) => option.trim()).filter(Boolean),
      correct_index: question.correct_index,
    }))
    if (normalized.some((question) => question.text.length < 2 || question.options.length < 2 || question.correct_index >= question.options.length)) {
      setError('Chaque question doit avoir au moins deux réponses et une bonne réponse valide.')
      return
    }

    setWorking(true)
    setError('')
    try {
      await createTeacherQuiz(sessionId, {
        title: title.trim(),
        assessment_type: assessmentType,
        duration_minutes: Number(duration),
        pass_pct: 80,
        questions: normalized,
      })
      setTitle('')
      setQuestions([emptyQuestion()])
      await refresh(sessionId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Création impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function changeStatus(quiz: TeacherQuiz, status: TeacherQuiz['status']) {
    try {
      const updated = await updateTeacherQuizStatus(quiz.id, status)
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Modification impossible.')
    }
  }

  async function openResults(quiz: TeacherQuiz) {
    try {
      setResults(await getTeacherQuizResults(quiz.id))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Résultats indisponibles.')
    }
  }

  return (
    <main className="app-page academic-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Espace professeur</span>
          <h1>Quiz & examens</h1>
          <p>Créez vos évaluations et consultez les résultats de la cohorte.</p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}

      <label className="academic-session-select">
        Session
        <select value={sessionId ?? ''} onChange={(event) => setSessionId(Number(event.target.value))}>
          {workspace?.sessions.map((session) => (
            <option key={session.session_id} value={session.session_id}>
              {session.formation_title} · {session.session_label}
            </option>
          ))}
        </select>
      </label>

      <section className="quiz-teacher-layout">
        <form className="app-card academic-form-card quiz-builder" onSubmit={create}>
          <span className="section-label">Nouvelle évaluation</span>
          <h2>Créer un quiz ou un examen</h2>
          <label>Titre<input value={title} onChange={(event) => setTitle(event.target.value)} required minLength={2}/></label>
          <div className="academic-form-row">
            <label>Type<select value={assessmentType} onChange={(event) => setAssessmentType(event.target.value as 'quiz' | 'exam')}><option value="quiz">Quiz</option><option value="exam">Examen</option></select></label>
            <label>Durée<select value={duration} onChange={(event) => setDuration(event.target.value)}><option value="15">15 min</option><option value="30">30 min</option><option value="45">45 min</option><option value="60">1 h</option><option value="90">1 h 30</option><option value="120">2 h</option></select></label>
          </div>

          <div className="quiz-question-builder">
            {questions.map((question, questionIndex) => (
              <article key={questionIndex}>
                <div className="quiz-question-builder-head">
                  <strong>Question {questionIndex + 1}</strong>
                  {questions.length > 1 && <button type="button" onClick={() => setQuestions((current) => current.filter((_, index) => index !== questionIndex))}><X size={13}/></button>}
                </div>
                <input value={question.text} onChange={(event) => changeQuestion(questionIndex, { text: event.target.value })} placeholder="Votre question" />
                {question.options.map((option, optionIndex) => (
                  <label className="quiz-option-builder" key={optionIndex}>
                    <input type="radio" name={'correct-' + questionIndex} checked={question.correct_index === optionIndex} onChange={() => changeQuestion(questionIndex, { correct_index: optionIndex })} />
                    <input value={option} onChange={(event) => changeOption(questionIndex, optionIndex, event.target.value)} placeholder={'Réponse ' + (optionIndex + 1)} />
                  </label>
                ))}
              </article>
            ))}
          </div>

          <button type="button" className="secondary-button" onClick={() => setQuestions((current) => [...current, emptyQuestion()])}><Plus size={13}/> Ajouter une question</button>
          <button className="primary-button" disabled={working}><Plus size={14}/>{working ? 'Création…' : 'Créer en brouillon'}</button>
        </form>

        <section className="academic-card-list">
          {items.map((quiz) => (
            <article className="app-card quiz-summary-card" key={quiz.id}>
              <div>
                <span className="section-label">{quiz.assessment_type === 'exam' ? 'Examen' : 'Quiz'} · {quiz.status}</span>
                <h3>{quiz.title}</h3>
                <small>Prof. {quiz.teacher_name || '—'}</small>
              </div>
              <div className="quiz-summary-meta">
                <span><Timer size={13}/>{quiz.duration_minutes || '—'} min</span>
                <span>{quiz.questions.length} question(s)</span>
                <span>{quiz.attempts_count} tentative(s)</span>
              </div>
              <div className="quiz-summary-actions">
                <select value={quiz.status} disabled={quiz.teacher_id !== null && quiz.teacher_name !== null && quiz.teacher_id !== items.find((item)=>item.id===quiz.id)?.teacher_id} onChange={(event) => void changeStatus(quiz, event.target.value as TeacherQuiz['status'])}>
                  <option value="draft">Brouillon</option>
                  <option value="active">Actif</option>
                  <option value="closed">Fermé</option>
                </select>
                <button type="button" className="secondary-button compact-action" onClick={() => void openResults(quiz)}><BarChart3 size={13}/> Résultats</button>
              </div>
            </article>
          ))}
          {items.length === 0 && <div className="app-card formation-empty"><CheckCircle2 size={26}/><strong>Aucune évaluation</strong><p>Créez votre premier quiz ou examen.</p></div>}
        </section>
      </section>

      {results && (
        <div className="assignment-modal-overlay" onClick={() => setResults(null)}>
          <div className="assignment-modal" onClick={(event) => event.stopPropagation()}>
            <header><div><span className="section-label">Résultats</span><h2>{results.title}</h2><p>{results.total_students} étudiant(s) inscrits</p></div><button type="button" onClick={() => setResults(null)}>×</button></header>
            <div className="submission-list">
              {results.attempts.map((attempt, index) => (
                <article className="submission-row quiz-result-row" key={index}>
                  <strong>{attempt.student_name}</strong>
                  <span>Tentative {attempt.attempt_number}</span>
                  <strong>{attempt.score_pct}%</strong>
                  <small>{new Date(attempt.submitted_at).toLocaleString('fr-FR')}</small>
                </article>
              ))}
              {results.attempts.length === 0 && <div className="empty-row">Aucune tentative.</div>}
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
