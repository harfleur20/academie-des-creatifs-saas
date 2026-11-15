import { useEffect, useState, type FormEvent } from 'react'
import {
  BarChart3,
  CheckCircle2,
  LoaderCircle,
  Plus,
  Sparkles,
  Timer,
  WandSparkles,
  X,
} from 'lucide-react'
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
import {
  generateTeacherQuizDraft,
  getTeacherAIStatus,
} from '../lib/tenantIntegrationApi'
import { initialTeacherSessionId } from '../lib/teacherSession'

// As on the mother site: one or several right answers, and points per question.
type DraftQuestion = {
  text: string
  options: [string, string, string, string]
  correct_index: number
  selection_mode: 'single' | 'multiple'
  correct_indices: number[]
  points: string
}

type CreationMode = 'manual' | 'ai'

const emptyQuestion = (): DraftQuestion => ({
  text: '',
  options: ['', '', '', ''],
  correct_index: 0,
  selection_mode: 'single',
  correct_indices: [],
  points: '1',
})

function fourOptions(options: string[]): [string, string, string, string] {
  return [options[0] || '', options[1] || '', options[2] || '', options[3] || '']
}

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
  const [showForm, setShowForm] = useState(false)
  const [creationMode, setCreationMode] = useState<CreationMode>('manual')

  const [aiConnected, setAiConnected] = useState<boolean | null>(null)
  const [aiTopic, setAiTopic] = useState('')
  const [aiLevel, setAiLevel] = useState('')
  const [aiObjectives, setAiObjectives] = useState('')
  const [aiQuestionCount, setAiQuestionCount] = useState(20)
  const [aiGenerating, setAiGenerating] = useState(false)

  useEffect(() => {
    Promise.all([
      getTeacherWorkspace(),
      getTeacherAIStatus().catch(() => null),
    ]).then(([data, aiStatus]) => {
      setWorkspace(data)
      setSessionId(initialTeacherSessionId(data.sessions))
      setAiConnected(aiStatus?.connected ?? false)
    }).catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [])

  async function refresh(id: number) {
    setItems(await listTeacherQuizzes(id))
  }

  useEffect(() => {
    if (sessionId) void refresh(sessionId).catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [sessionId])

  function resetForm() {
    setTitle('')
    setAssessmentType('quiz')
    setDuration('30')
    setQuestions([emptyQuestion()])
    setCreationMode('manual')
    setAiTopic('')
    setAiLevel('')
    setAiObjectives('')
    setAiQuestionCount(20)
  }

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

  async function generateWithAI() {
    if (!sessionId || !aiTopic.trim()) return
    setAiGenerating(true)
    setError('')
    try {
      const draft = await generateTeacherQuizDraft({
        session_id: sessionId,
        topic: aiTopic.trim(),
        level: aiLevel.trim() || null,
        objectives: aiObjectives.trim() || null,
        questions_count: aiQuestionCount,
        options_per_question: 4,
      })
      setTitle(draft.title)
      setDuration(String(draft.duration_minutes || 30))
      setQuestions(draft.questions.map((question) => ({
        text: question.text,
        options: fourOptions(question.options),
        correct_index: Math.max(0, Math.min(3, question.correct_index)),
        selection_mode: 'single',
        correct_indices: [],
        points: '1',
      })))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Impossible de générer le quiz.')
    } finally {
      setAiGenerating(false)
    }
  }

  async function create(event: FormEvent) {
    event.preventDefault()
    if (!sessionId) return
    const normalized = questions.map((question) => {
      const multiple = question.selection_mode === 'multiple'
      const correctIndices = [...question.correct_indices].sort((a, b) => a - b)
      return {
        text: question.text.trim(),
        options: question.options.map((option) => option.trim()).filter(Boolean),
        correct_index: multiple ? correctIndices[0] ?? 0 : question.correct_index,
        selection_mode: question.selection_mode,
        correct_indices: multiple ? correctIndices : undefined,
        points: Number(question.points.replace(',', '.')),
      }
    })
    if (normalized.some((question) => question.text.length < 2 || question.options.length < 4 || question.correct_index >= question.options.length)) {
      setError('Chaque question doit avoir au moins quatre réponses et une bonne réponse valide.')
      return
    }
    if (normalized.some((question) => question.selection_mode === 'multiple' && !question.correct_indices?.length)) {
      setError('Cochez au moins une bonne réponse pour chaque question à plusieurs réponses.')
      return
    }
    if (normalized.some((question) => !(question.points > 0 && question.points <= 100))) {
      setError('Chaque question vaut entre 0,5 et 100 points.')
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
      resetForm()
      setShowForm(false)
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
    <main className="app-page teacher-mother-page">
      <div className="dsh-page teacher-dsh-page">
        <div className="teacher-page-head">
          <div><h1>Quiz & examens</h1><p>Créez vos évaluations et consultez les résultats de la cohorte.</p></div>
          <button className="dsh-btn dsh-btn--primary" type="button" disabled={!sessionId} onClick={() => setShowForm(true)}><Plus size={14} /> Nouvelle évaluation</button>
        </div>

        {error && <div className="dsh-error">{error}</div>}

        <label className="teacher-session-select">
          <span>Session</span>
          <select value={sessionId ?? ''} onChange={(event) => setSessionId(Number(event.target.value))}>
            {workspace?.sessions.map((session) => <option key={session.session_id} value={session.session_id}>{session.formation_title} · {session.session_label}</option>)}
          </select>
        </label>

        <div className="dsh-list teacher-quiz-list">
          {items.map((quiz) => (
            <article className="dsh-list-item teacher-quiz-row" key={quiz.id}>
              <div className="dsh-list-item__main">
                <div className="teacher-assignment-title-row"><strong>{quiz.title}</strong><span className={`dsh-badge ${quiz.status === 'active' ? 'dsh-badge--green' : quiz.status === 'closed' ? 'dsh-badge--gray' : 'dsh-badge--yellow'}`}>{quiz.status === 'active' ? 'Actif' : quiz.status === 'closed' ? 'Fermé' : 'Brouillon'}</span></div>
                <span className="dsh-list-item__meta">{quiz.assessment_type === 'exam' ? 'Examen' : 'Quiz'} · Prof. {quiz.teacher_name || '-'}</span>
                <span className="dsh-list-item__meta"><Timer size={12} /> {quiz.duration_minutes || '-'} min · {quiz.questions.length} question(s) · {quiz.attempts_count} tentative(s)</span>
              </div>
              <div className="dsh-list-item__actions teacher-quiz-actions">
                <select value={quiz.status} onChange={(event) => void changeStatus(quiz, event.target.value as TeacherQuiz['status'])}><option value="draft">Brouillon</option><option value="active">Actif</option><option value="closed">Fermé</option></select>
                <button className="dsh-btn dsh-btn--outline dsh-btn--sm" type="button" onClick={() => void openResults(quiz)}><BarChart3 size={13} /> Résultats</button>
              </div>
            </article>
          ))}
          {items.length === 0 && <div className="dsh-empty"><CheckCircle2 size={26} /><strong>Aucune évaluation</strong><p>Créez votre premier quiz ou examen.</p></div>}
        </div>
      </div>

      {showForm && (
        <div className="dsh-modal-overlay" onClick={() => !working && !aiGenerating && setShowForm(false)}>
          <form className="dsh-modal dsh-modal--xlarge teacher-create-modal teacher-quiz-builder-modal" onSubmit={create} onClick={(event) => event.stopPropagation()}>
            <div className="dsh-modal__header"><div><span className="section-label">Évaluation</span><h3>Créer un quiz ou un examen</h3></div><button className="dsh-icon-btn" type="button" disabled={working || aiGenerating} onClick={() => setShowForm(false)}><X size={16} /></button></div>

            <div className="teacher-create-tabs">
              <button type="button" className={creationMode === 'manual' ? 'is-active' : ''} onClick={() => setCreationMode('manual')}>Manuel</button>
              <button type="button" className={creationMode === 'ai' ? 'is-active' : ''} onClick={() => setCreationMode('ai')}><WandSparkles size={14} /> Avec IA</button>
            </div>

            <div className="teacher-create-body">
              {creationMode === 'ai' && (
                <section className="teacher-ai-panel">
                  <div className="teacher-ai-title"><Sparkles size={17} /><div><strong>Générer les questions avec l’IA</strong><span>Le professeur relit toutes les réponses avant publication.</span></div></div>
                  {aiConnected === false ? <div className="teacher-ai-unavailable">OpenAI n’est pas connecté pour cette école. Demandez à un administrateur de l’activer dans Connect.</div> : <>
                    <label>Sujet / contenu à évaluer<textarea value={aiTopic} onChange={(event) => setAiTopic(event.target.value)} placeholder="Ex. Fondamentaux de Docker, images, conteneurs et volumes" /></label>
                    <div className="teacher-form-grid two-columns"><label>Niveau<input value={aiLevel} onChange={(event) => setAiLevel(event.target.value)} placeholder="Intermédiaire" /></label><label>Nombre de questions<select value={aiQuestionCount} onChange={(event) => setAiQuestionCount(Number(event.target.value))}><option value={10}>10</option><option value={20}>20</option><option value={40}>40</option></select></label></div>
                    <label>Objectifs évalués<textarea value={aiObjectives} onChange={(event) => setAiObjectives(event.target.value)} placeholder="Ex. Comprendre le cycle de vie d’un conteneur…" /></label>
                    <button className="dsh-btn dsh-btn--ai" type="button" disabled={aiGenerating || !aiTopic.trim()} onClick={() => void generateWithAI()}>{aiGenerating ? <LoaderCircle className="openai-spin" size={14} /> : <WandSparkles size={14} />} {aiGenerating ? 'Génération…' : 'Générer les questions'}</button>
                  </>}
                </section>
              )}

              <section className="teacher-manual-fields">
                <label>Titre<input value={title} onChange={(event) => setTitle(event.target.value)} required minLength={2} /></label>
                <div className="teacher-form-grid two-columns"><label>Type<select value={assessmentType} onChange={(event) => setAssessmentType(event.target.value as 'quiz' | 'exam')}><option value="quiz">Quiz</option><option value="exam">Examen</option></select></label><label>Durée<select value={duration} onChange={(event) => setDuration(event.target.value)}><option value="15">15 min</option><option value="30">30 min</option><option value="45">45 min</option><option value="60">1 h</option><option value="90">1 h 30</option><option value="120">2 h</option></select></label></div>

                <div className="teacher-question-builder">
                  {questions.map((question, questionIndex) => (
                    <article key={questionIndex}>
                      <div className="teacher-question-head"><strong>Question {questionIndex + 1}</strong>{questions.length > 1 && <button className="dsh-icon-btn" type="button" onClick={() => setQuestions((current) => current.filter((_, index) => index !== questionIndex))}><X size={13} /></button>}</div>
                      <input value={question.text} onChange={(event) => changeQuestion(questionIndex, { text: event.target.value })} placeholder="Votre question" />
                      <div className="teacher-question-settings">
                        <label>Réponses
                          <select value={question.selection_mode} onChange={(event) => changeQuestion(questionIndex, {
                            selection_mode: event.target.value as DraftQuestion['selection_mode'],
                            correct_indices: event.target.value === 'multiple' ? [question.correct_index] : [],
                          })}>
                            <option value="single">Une bonne réponse</option>
                            <option value="multiple">Plusieurs bonnes réponses</option>
                          </select>
                        </label>
                        <label>Points<input type="number" min="0.5" max="100" step="0.5" value={question.points} onChange={(event) => changeQuestion(questionIndex, { points: event.target.value })} /></label>
                      </div>
                      <div className="teacher-question-options">{question.options.map((option, optionIndex) => {
                        const multiple = question.selection_mode === 'multiple'
                        const correct = multiple ? question.correct_indices.includes(optionIndex) : question.correct_index === optionIndex
                        return <label className={correct ? 'is-correct' : ''} key={optionIndex}>
                          <input
                            type={multiple ? 'checkbox' : 'radio'}
                            name={`correct-${questionIndex}`}
                            aria-label={`Réponse ${optionIndex + 1} correcte`}
                            checked={correct}
                            onChange={() => changeQuestion(questionIndex, multiple
                              ? { correct_indices: correct ? question.correct_indices.filter((value) => value !== optionIndex) : [...question.correct_indices, optionIndex] }
                              : { correct_index: optionIndex })}
                          />
                          <input value={option} onChange={(event) => changeOption(questionIndex, optionIndex, event.target.value)} placeholder={`Réponse ${optionIndex + 1}`} />
                        </label>
                      })}</div>
                      {question.selection_mode === 'multiple' && <small className="teacher-question-help">Chaque bonne réponse cochée rapporte une part des points, chaque mauvaise en retire autant, sans descendre sous zéro.</small>}
                    </article>
                  ))}
                </div>
                <button type="button" className="dsh-btn dsh-btn--outline" onClick={() => setQuestions((current) => [...current, emptyQuestion()])}><Plus size={13} /> Ajouter une question</button>
              </section>
            </div>

            <div className="dsh-modal__footer"><button className="dsh-btn dsh-btn--ghost" type="button" disabled={working} onClick={() => setShowForm(false)}>Annuler</button><button className="dsh-btn dsh-btn--primary" disabled={working || !title.trim()}><Plus size={14} /> {working ? 'Création…' : 'Créer en brouillon'}</button></div>
          </form>
        </div>
      )}

      {results && (
        <div className="dsh-modal-overlay" onClick={() => setResults(null)}>
          <div className="dsh-modal dsh-modal--large teacher-results-modal" onClick={(event) => event.stopPropagation()}>
            <div className="dsh-modal__header"><div><span className="section-label">Résultats</span><h3>{results.title}</h3><p>{results.total_students} étudiant(s) inscrits</p></div><button className="dsh-icon-btn" type="button" onClick={() => setResults(null)}><X size={16} /></button></div>
            <div className="teacher-results-list">{results.attempts.map((attempt, index) => <article key={index}><strong>{attempt.student_name}</strong><span>Tentative {attempt.attempt_number}</span><strong>{attempt.score_pct}%</strong><small>{new Date(attempt.submitted_at).toLocaleString('fr-FR')}</small></article>)}{results.attempts.length === 0 && <div className="dsh-empty">Aucune tentative.</div>}</div>
          </div>
        </div>
      )}
    </main>
  )
}
