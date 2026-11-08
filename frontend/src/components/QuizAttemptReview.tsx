import { CheckCircle2, XCircle } from 'lucide-react'
import type { QuizAttempt, StudentQuizQuestion } from '../lib/api'

/** The correction of one attempt: the student's answer and the right one, question by question. */
export function QuizAttemptReview({
  questions,
  attempt,
  passPct,
}: {
  questions: StudentQuizQuestion[]
  attempt: QuizAttempt
  passPct: number
}) {
  const passed = attempt.score_pct >= passPct
  const correctCount = questions.filter(
    (_, index) => attempt.submitted_answers[index] === attempt.correct_answers[index],
  ).length

  return (
    <div className="quiz-review">
      <div className={`quiz-review__hero${passed ? ' is-pass' : ' is-fail'}`}>
        <strong>{Math.round(attempt.score_pct)} %</strong>
        <span>
          {passed ? 'Quiz validé.' : 'Quiz non validé.'} Tentative {attempt.attempt_number} · {correctCount} bonne(s) réponse(s) sur {questions.length}.
        </span>
      </div>
      <ol className="quiz-review__list">
        {questions.map((question, index) => {
          const selected = attempt.submitted_answers[index]
          const correct = attempt.correct_answers[index]
          const isCorrect = selected === correct
          return (
            <li className={`quiz-review__item${isCorrect ? ' is-correct' : ' is-wrong'}`} key={question.id}>
              <div className="quiz-review__head">
                <strong>{index + 1}. {question.text}</strong>
                <span>{isCorrect ? <><CheckCircle2 size={13} /> Correct</> : <><XCircle size={13} /> À revoir</>}</span>
              </div>
              <span>Votre réponse : {question.options[selected] ?? 'Aucune'}</span>
              {!isCorrect && <span>Bonne réponse : {question.options[correct] ?? '—'}</span>}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
