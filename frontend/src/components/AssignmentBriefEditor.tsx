import { Plus, Trash2 } from 'lucide-react'
import type { AssignmentBrief, AssignmentRubricCriterion } from '../lib/api'

const MAX_CRITERIA = 8

export function emptyAssignmentBrief(): AssignmentBrief {
  return {
    context: '',
    objective: '',
    deliverables: [''],
    steps: [''],
    evaluation_criteria: [{ label: '', points: 20, description: '' }],
    submission_method: '',
    tips: [],
  }
}

function cleanLines(values: string[]) {
  return values.map((item) => item.trim()).filter(Boolean)
}

/** The editor keeps blank lines while the teacher types; they are dropped here, on saving. */
export function cleanAssignmentBrief(brief: AssignmentBrief): AssignmentBrief {
  return {
    context: brief.context.trim(),
    objective: brief.objective.trim(),
    deliverables: cleanLines(brief.deliverables),
    steps: cleanLines(brief.steps),
    evaluation_criteria: brief.evaluation_criteria.map((item) => ({
      label: item.label.trim(),
      points: Number(item.points),
      description: item.description.trim(),
    })),
    submission_method: brief.submission_method.trim(),
    tips: cleanLines(brief.tips),
  }
}

function scaleTotal(brief: AssignmentBrief) {
  return brief.evaluation_criteria.reduce((sum, item) => sum + (Number(item.points) || 0), 0)
}

export function assignmentBriefProblem(brief: AssignmentBrief): string | null {
  if (!brief.objective) return 'Renseignez l’objectif de la fiche TP.'
  if (brief.deliverables.length === 0) return 'Ajoutez au moins un livrable.'
  if (brief.deliverables.length > 8) return 'Une fiche TP compte au plus 8 livrables.'
  if (brief.steps.length === 0) return 'Ajoutez au moins une étape.'
  if (brief.steps.length > 8) return 'Une fiche TP compte au plus 8 étapes.'
  if (brief.tips.length > 6) return 'Une fiche TP compte au plus 6 conseils.'
  if (brief.evaluation_criteria.length === 0) return 'Ajoutez au moins un critère d’évaluation.'
  if (brief.evaluation_criteria.some((item) => !item.label || !item.description)) {
    return 'Chaque critère doit avoir un nom et une description.'
  }
  if (brief.evaluation_criteria.some((item) => !(item.points > 0 && item.points <= 20))) {
    return 'Chaque critère vaut entre 0 et 20 points.'
  }
  if (Math.abs(scaleTotal(brief) - 20) > 0.01) return 'Le barème doit totaliser exactement 20 points.'
  if (!brief.submission_method) return 'Précisez la modalité de rendu.'
  return null
}

export function assignmentBriefToText(brief: AssignmentBrief) {
  const list = (title: string, items: string[]) => (items.length ? [title, ...items.map((item) => `- ${item}`), ''] : [])
  return [
    ...(brief.context ? ['Contexte', brief.context, ''] : []),
    ...(brief.objective ? ['Objectif', brief.objective, ''] : []),
    ...list('Livrables attendus', cleanLines(brief.deliverables)),
    ...list('Étapes recommandées', cleanLines(brief.steps)),
    ...list(
      'Critères d’évaluation',
      brief.evaluation_criteria
        .filter((item) => item.label)
        .map((item) => `${item.label} (${item.points}/20) : ${item.description}`),
    ),
    ...(brief.submission_method ? ['Modalité de rendu', brief.submission_method, ''] : []),
    ...list('Conseils', cleanLines(brief.tips)),
  ].join('\n').trim()
}

export function AssignmentBriefEditor({
  brief,
  onChange,
}: {
  brief: AssignmentBrief
  onChange: (brief: AssignmentBrief) => void
}) {
  const total = scaleTotal(brief)

  function updateCriterion(index: number, patch: Partial<AssignmentRubricCriterion>) {
    onChange({
      ...brief,
      evaluation_criteria: brief.evaluation_criteria.map((item, itemIndex) => (
        itemIndex === index ? { ...item, ...patch } : item
      )),
    })
  }

  return (
    <div className="asg-brief-editor">
      <label>Contexte<textarea rows={3} maxLength={800} value={brief.context} onChange={(event) => onChange({ ...brief, context: event.target.value })} placeholder="Contexte court, sans répéter l’objectif." /></label>
      <label>Objectif<textarea rows={3} maxLength={600} value={brief.objective} onChange={(event) => onChange({ ...brief, objective: event.target.value })} placeholder="Mission claire et mesurable." /></label>
      <label>Livrables attendus<textarea rows={4} value={brief.deliverables.join('\n')} onChange={(event) => onChange({ ...brief, deliverables: event.target.value.split('\n') })} placeholder="Un livrable par ligne" /></label>
      <label>Étapes recommandées<textarea rows={5} value={brief.steps.join('\n')} onChange={(event) => onChange({ ...brief, steps: event.target.value.split('\n') })} placeholder="Une étape par ligne" /></label>

      <fieldset className="asg-brief-editor__rubric">
        <legend>Critères d’évaluation</legend>
        {brief.evaluation_criteria.map((criterion, index) => (
          <div className="asg-brief-editor__criterion" key={index}>
            <input aria-label={`Nom du critère ${index + 1}`} maxLength={100} value={criterion.label} onChange={(event) => updateCriterion(index, { label: event.target.value })} placeholder="Critère" />
            <input aria-label={`Points du critère ${index + 1}`} type="number" min={0.5} max={20} step={0.5} value={criterion.points} onChange={(event) => updateCriterion(index, { points: Number(event.target.value) })} />
            <button
              className="dsh-icon-btn"
              type="button"
              title="Supprimer ce critère"
              aria-label={`Supprimer le critère ${index + 1}`}
              onClick={() => onChange({ ...brief, evaluation_criteria: brief.evaluation_criteria.filter((_, itemIndex) => itemIndex !== index) })}
            >
              <Trash2 size={14} />
            </button>
            <textarea aria-label={`Description du critère ${index + 1}`} rows={2} maxLength={320} value={criterion.description} onChange={(event) => updateCriterion(index, { description: event.target.value })} placeholder="Ce qui est attendu" />
          </div>
        ))}
        <div className="asg-brief-editor__rubric-footer">
          <button
            className="dsh-btn dsh-btn--ghost dsh-btn--sm"
            type="button"
            disabled={brief.evaluation_criteria.length >= MAX_CRITERIA}
            onClick={() => onChange({ ...brief, evaluation_criteria: [...brief.evaluation_criteria, { label: '', points: 1, description: '' }] })}
          >
            <Plus size={14} /> Ajouter un critère
          </button>
          <strong className={Math.abs(total - 20) > 0.01 ? 'is-invalid' : ''}>Total : {total}/20</strong>
        </div>
      </fieldset>

      <label>Modalité de rendu<textarea rows={2} maxLength={400} value={brief.submission_method} onChange={(event) => onChange({ ...brief, submission_method: event.target.value })} placeholder="Format, fichiers attendus et mode de dépôt." /></label>
      <label>Conseils<textarea rows={3} value={brief.tips.join('\n')} onChange={(event) => onChange({ ...brief, tips: event.target.value.split('\n') })} placeholder="Un conseil par ligne (facultatif)" /></label>
    </div>
  )
}
