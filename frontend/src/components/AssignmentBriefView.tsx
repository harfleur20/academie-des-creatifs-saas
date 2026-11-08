import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import type { AssignmentBrief } from '../lib/api'

const PREVIEW_LENGTH = 220

function BriefSections({ brief }: { brief: AssignmentBrief }) {
  return (
    <div className="asg-brief__content">
      {brief.context && (
        <section>
          <h4>Contexte</h4>
          <p>{brief.context}</p>
        </section>
      )}
      <section>
        <h4>Objectif</h4>
        <p>{brief.objective}</p>
      </section>
      <section>
        <h4>Livrables attendus</h4>
        <ul>{brief.deliverables.map((item) => <li key={item}>{item}</li>)}</ul>
      </section>
      <section>
        <h4>Étapes recommandées</h4>
        <ol>{brief.steps.map((item) => <li key={item}>{item}</li>)}</ol>
      </section>
      <section>
        <h4>Critères d’évaluation</h4>
        <div className="asg-brief__rubric">
          {brief.evaluation_criteria.map((criterion) => (
            <div className="asg-brief__criterion" key={criterion.label}>
              <div>
                <strong>{criterion.label}</strong>
                <p>{criterion.description}</p>
              </div>
              <b>{criterion.points}/20</b>
            </div>
          ))}
        </div>
      </section>
      <section>
        <h4>Modalité de rendu</h4>
        <p>{brief.submission_method}</p>
      </section>
      {brief.tips.length > 0 && (
        <section>
          <h4>Conseils</h4>
          <ul>{brief.tips.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
      )}
    </div>
  )
}

export function AssignmentBriefView({
  brief,
  instructions,
  collapsible = true,
}: {
  brief?: AssignmentBrief | null
  instructions?: string | null
  collapsible?: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const freeText = (instructions ?? '').trim()
  if (!brief && !freeText) return null

  const open = !collapsible || expanded
  const canToggle = collapsible && (Boolean(brief) || freeText.length > PREVIEW_LENGTH)

  return (
    <div className="asg-brief">
      {!open && <p className="asg-brief__preview">{brief?.objective ?? freeText}</p>}
      {open && brief && <BriefSections brief={brief} />}
      {open && !brief && <p className="asg-brief__free-text">{freeText}</p>}
      {canToggle && (
        <button className="asg-brief__toggle" type="button" onClick={() => setExpanded((value) => !value)}>
          {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          {expanded ? 'Réduire' : 'Voir le détail'}
        </button>
      )}
    </div>
  )
}
