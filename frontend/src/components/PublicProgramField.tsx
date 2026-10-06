import { useMemo, useState } from 'react'
import { Edit3 } from 'lucide-react'
import { getFormation, updateFormation, type FormationDetail } from '../lib/api'
import { PublicProgramEditorModal, summarizePublicProgram } from './PublicProgramEditorModal'

export function PublicProgramField({
  formationId,
  value,
  disabled = false,
  onSaved,
}: {
  formationId: number
  value: string
  disabled?: boolean
  onSaved: (formation: FormationDetail) => void
}) {
  const [open, setOpen] = useState(false)
  const summary = useMemo(() => summarizePublicProgram(value), [value])

  const summaryLabel = summary.moduleCount > 0
    ? `${summary.moduleCount} module(s) · ${summary.chapterCount} chapitre(s) · ${summary.lessonCount} leçon(s)`
    : summary.hasLegacyIntroOnly
      ? 'Ancien programme texte à structurer'
      : 'Programme à construire'

  async function save(nextValue: string) {
    await updateFormation(formationId, { public_program: nextValue })
    const detail = await getFormation(formationId)
    onSaved(detail)
  }

  return (
    <>
      <div className="formation-public-program-card">
        <div>
          <span className="section-label">Programme public</span>
          <strong>{summaryLabel}</strong>
          <small>Construisez la structure Module → Chapitre → Leçon qui sera affichée en accordéon sur la fiche publique.</small>
          {summary.moduleCount > 0 && (
            <div className="formation-public-program-stats" aria-label="Résumé du programme public">
              <span>{summary.moduleCount} module(s)</span>
              <span>{summary.chapterCount} chapitre(s)</span>
              <span>{summary.lessonCount} leçon(s)</span>
            </div>
          )}
        </div>
        <button className="secondary-button" type="button" disabled={disabled} onClick={() => setOpen(true)}>
          <Edit3 size={15} /> {summary.moduleCount > 0 ? 'Modifier le programme' : 'Construire le programme'}
        </button>
      </div>

      <PublicProgramEditorModal
        open={open}
        value={value}
        onClose={() => setOpen(false)}
        onSave={save}
      />
    </>
  )
}
