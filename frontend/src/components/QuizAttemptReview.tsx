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
  const isRight = (index: number) => sameOptions(attempt.submitted_answers[index], attempt.correct_answers[index])
  const correctCount = questions.filter((_, index) => isRight(index)).length

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
          const isCorrect = isRight(index)
          const multiple = question.selection_mode === 'multiple'
          return (
            <li className={`quiz-review__item${isCorrect ? ' is-correct' : ' is-wrong'}`} key={question.id}>
              <div className="quiz-review__head">
                <strong>{index + 1}. {question.text}</strong>
                <span>{isCorrect ? <><CheckCircle2 size={13} /> Correct</> : <><XCircle size={13} /> À revoir</>}</span>
              </div>
              <span>{multiple ? 'Vos réponses' : 'Votre réponse'} : {optionLabels(question, attempt.submitted_answers[index]) || 'Aucune'}</span>
              {!isCorrect && <span>{multiple ? 'Bonnes réponses' : 'Bonne réponse'} : {optionLabels(question, attempt.correct_answers[index]) || '—'}</span>}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

function sameOptions(picked: number[] = [], right: number[] = []) {
  return picked.length === right.length && picked.every((option) => right.includes(option))
}

function optionLabels(question: StudentQuizQuestion, options: number[] = []) {
  return options.map((option) => question.options[option]).filter(Boolean).join(', ')
}
