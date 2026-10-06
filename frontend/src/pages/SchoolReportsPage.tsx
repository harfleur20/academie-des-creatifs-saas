import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  Banknote,
  BarChart3,
  BookOpen,
  CalendarDays,
  Download,
  FileText,
  GraduationCap,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import {
  ApiError,
  getCommercialDashboard,
  getSchoolPedagogyOverview,
  listFormations,
  type CommercialDashboard,
  type FormationSummary,
  type SchoolPedagogyOverview,
} from '../lib/api'
import { downloadSchoolReportPdf } from '../lib/reportPdf'
import { formatSchoolMoney } from '../public/publicHelpers'
import '../reports-connect.css'

const errorMessage = (error: unknown) => error instanceof ApiError ? error.message : 'Chargement impossible.'

type ReportKind = 'executive' | 'commerce' | 'catalogue' | 'sessions'

export function SchoolReportsPage() {
  const { activeOrganization } = useTenant()
  const [pedagogy, setPedagogy] = useState<SchoolPedagogyOverview | null>(null)
  const [commerce, setCommerce] = useState<CommercialDashboard | null>(null)
  const [formations, setFormations] = useState<FormationSummary[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [pdfError, setPdfError] = useState('')
  const [downloadingReport, setDownloadingReport] = useState<ReportKind | null>(null)

  useEffect(() => {
    let active = true
    void Promise.allSettled([getSchoolPedagogyOverview(), getCommercialDashboard(), listFormations()])
      .then(([pedagogyResult, commerceResult, formationsResult]) => {
        if (!active) return
        const messages: string[] = []
        if (pedagogyResult.status === 'fulfilled') setPedagogy(pedagogyResult.value)
        else messages.push(`Suivi pédagogique : ${errorMessage(pedagogyResult.reason)}`)
        if (commerceResult.status === 'fulfilled') setCommerce(commerceResult.value)
        else messages.push(`Commerce : ${errorMessage(commerceResult.reason)}`)
        if (formationsResult.status === 'fulfilled') setFormations(formationsResult.value)
        else messages.push(`Catalogue : ${errorMessage(formationsResult.reason)}`)
        setError(messages.join(' · '))
        setLoading(false)
      })
    return () => { active = false }
  }, [])

  const published = formations?.filter((formation) => formation.status === 'published').length ?? 0
  const drafts = formations?.filter((formation) => formation.status === 'draft').length ?? 0
  const archived = formations?.filter((formation) => formation.status === 'archived').length ?? 0
  const sessionsToWatch = pedagogy?.sessions.filter((row) => row.at_risk_count > 0 || row.pending_reviews_count > 0) ?? []
  const alerts = sessionsToWatch.length + (commerce?.late_installments ?? 0) + (pedagogy?.at_risk_students ?? 0)
  const collected = commerce?.totals_by_currency.length
    ? commerce.totals_by_currency.map((row) => formatSchoolMoney(row.collected_cents, row.currency)).join(' · ')
    : '—'
  const outstanding = commerce?.totals_by_currency.length
    ? commerce.totals_by_currency.map((row) => formatSchoolMoney(row.outstanding_cents, row.currency)).join(' · ')
    : '—'

  async function downloadReport(kind: ReportKind) {
    if (!activeOrganization) return
    setDownloadingReport(kind)
    setPdfError('')

    try {
      const common = {
        schoolName: activeOrganization.name,
        schoolLogoUrl: activeOrganization.logo_url,
      }

      if (kind === 'executive') {
        await downloadSchoolReportPdf({
          ...common,
          title: 'Synthèse direction',
          filename: `${activeOrganization.slug}-synthese-direction`,
          subtitle: 'Vue consolidée des principaux indicateurs de pilotage de l’école.',
          sections: [
            {
              title: 'Vue d’ensemble',
              rows: [
                { label: 'Catalogue', value: formations ? `${published} formation(s) publiée(s), ${drafts} à finaliser, ${archived} archivée(s).` : 'Donnée indisponible.' },
                { label: 'Commerce', value: commerce ? `${commerce.paid_order_count}/${commerce.order_count} commande(s) réglée(s). Encaissements : ${collected}. Reste à encaisser : ${outstanding}.` : 'Donnée indisponible.' },
                { label: 'Sessions', value: pedagogy ? `${pedagogy.active_sessions} session(s) active(s), ${sessionsToWatch.length} à surveiller.` : 'Donnée indisponible.' },
                { label: 'Alertes', value: `${alerts} signal(aux) nécessitent une vérification.` },
              ],
            },
            {
              title: 'Indicateurs de qualité',
              rows: [
                { label: 'Étudiants actifs', value: String(pedagogy?.active_students ?? commerce?.active_students ?? '—') },
                { label: 'Progression moyenne', value: pedagogy ? `${pedagogy.average_progress_pct}%` : '—' },
                { label: 'Présence moyenne', value: pedagogy?.average_attendance_pct == null ? '—' : `${pedagogy.average_attendance_pct}%` },
                { label: 'Étudiants à risque', value: String(pedagogy?.at_risk_students ?? '—') },
              ],
            },
          ],
        })
      }

      if (kind === 'commerce') {
        await downloadSchoolReportPdf({
          ...common,
          title: 'Rapport commercial',
          filename: `${activeOrganization.slug}-rapport-commercial`,
          subtitle: 'Situation des commandes, paiements et encaissements de l’école.',
          sections: [
            {
              title: 'Situation commerciale',
              rows: [
                { label: 'Commandes', value: commerce ? String(commerce.order_count) : '—' },
                { label: 'Commandes réglées', value: commerce ? String(commerce.paid_order_count) : '—' },
                { label: 'Échéances en retard', value: commerce ? String(commerce.late_installments) : '—' },
                { label: 'Encaissements', value: collected },
                { label: 'Reste à encaisser', value: outstanding },
                { label: 'Étudiants actifs', value: commerce ? String(commerce.active_students) : '—' },
              ],
            },
          ],
        })
      }

      if (kind === 'catalogue') {
        await downloadSchoolReportPdf({
          ...common,
          title: 'Rapport catalogue',
          filename: `${activeOrganization.slug}-rapport-catalogue`,
          subtitle: 'État de publication et d’exploitation des formations de l’école.',
          sections: [
            {
              title: 'Résumé du catalogue',
              rows: [
                { label: 'Total', value: formations ? String(formations.length) : '—' },
                { label: 'Publiées', value: String(published) },
                { label: 'À finaliser', value: String(drafts) },
                { label: 'Archivées', value: String(archived) },
              ],
            },
            {
              title: 'Détail des formations',
              rows: (formations ?? []).map((formation) => ({
                label: formation.title,
                value: `${formation.status === 'published' ? 'Publiée' : formation.status === 'archived' ? 'Archivée' : 'Brouillon'} · ${formation.student_count} étudiant(s) · ${formation.teacher_count} enseignant(s) · ${formation.course_count} cours · ${formation.session_count} session(s)`,
              })),
            },
          ],
        })
      }

      if (kind === 'sessions') {
        await downloadSchoolReportPdf({
          ...common,
          title: 'Rapport des sessions à surveiller',
          filename: `${activeOrganization.slug}-sessions-a-surveiller`,
          subtitle: 'Vue de supervision des sessions présentant des signaux nécessitant une vérification de l’administration.',
          sections: [
            {
              title: 'Synthèse',
              rows: [
                { label: 'Sessions actives', value: pedagogy ? String(pedagogy.active_sessions) : '—' },
                { label: 'Sessions à surveiller', value: String(sessionsToWatch.length) },
                { label: 'Étudiants à risque', value: pedagogy ? String(pedagogy.at_risk_students) : '—' },
              ],
            },
            {
              title: 'Détail des sessions',
              rows: sessionsToWatch.length > 0
                ? sessionsToWatch.map((row) => ({
                    label: row.session_label || row.formation_title,
                    value: `${row.formation_title} · ${row.at_risk_count} étudiant(s) à risque · ${row.pending_reviews_count} correction(s) en attente · remplissage ${row.fill_rate_pct}% · présence ${row.attendance_rate_pct == null ? '—' : `${row.attendance_rate_pct}%`}`,
                  }))
                : [{ label: 'État', value: 'Aucune session ne présente actuellement de signal particulier.' }],
            },
          ],
        })
      }
    } catch (err) {
      setPdfError(err instanceof Error ? err.message : 'Impossible de générer ce rapport PDF.')
    } finally {
      setDownloadingReport(null)
    }
  }

  return (
    <main className="app-page school-reports-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">Direction & supervision</span>
          <h1>Rapports</h1>
          <p>Une synthèse claire pour savoir où en est votre école, ce qui fonctionne et les points qui demandent votre attention.</p>
        </div>
      </header>

      {loading && <div className="page-state">Préparation des rapports…</div>}
      {error && <div className="form-error">{error}</div>}
      {pdfError && <div className="form-error">{pdfError}</div>}

      {!loading && (
        <>
          <section className="reports-download-panel app-card">
            <div className="reports-download-heading">
              <div>
                <span className="section-label">Exports PDF</span>
                <h2>Rapports à télécharger</h2>
                <p>Chaque PDF reprend automatiquement le logo et le nom de l’école dans son en-tête.</p>
              </div>
              <Download size={21} />
            </div>
            <div className="reports-download-grid">
              <button type="button" onClick={() => void downloadReport('executive')} disabled={downloadingReport !== null}>
                <FileText size={18} /><span><strong>Synthèse direction</strong><small>Vue globale de l’école</small></span><Download size={16} />
              </button>
              <button type="button" onClick={() => void downloadReport('commerce')} disabled={downloadingReport !== null}>
                <Banknote size={18} /><span><strong>Rapport commercial</strong><small>Paiements et encaissements</small></span><Download size={16} />
              </button>
              <button type="button" onClick={() => void downloadReport('catalogue')} disabled={downloadingReport !== null}>
                <BookOpen size={18} /><span><strong>Rapport catalogue</strong><small>État des formations</small></span><Download size={16} />
              </button>
              <button type="button" onClick={() => void downloadReport('sessions')} disabled={downloadingReport !== null}>
                <CalendarDays size={18} /><span><strong>Sessions à surveiller</strong><small>Signaux de supervision</small></span><Download size={16} />
              </button>
            </div>
            {downloadingReport && <small className="reports-download-status">Génération du PDF en cours…</small>}
          </section>

          <section className="reports-summary-grid">
            <article className="app-card reports-summary-card">
              <span><GraduationCap size={17} /> Catalogue</span>
              <strong>{formations ? `${published}/${formations.length}` : '—'}</strong>
              <small>{formations ? `${drafts} formation(s) à finaliser` : 'Donnée indisponible'}</small>
            </article>
            <article className="app-card reports-summary-card">
              <span><Banknote size={17} /> Encaissements</span>
              <strong>{collected}</strong>
              <small>{commerce ? `${commerce.paid_order_count}/${commerce.order_count} commande(s) réglée(s)` : 'Donnée indisponible'}</small>
            </article>
            <article className="app-card reports-summary-card">
              <span><CalendarDays size={17} /> Sessions à surveiller</span>
              <strong>{pedagogy ? sessionsToWatch.length : '—'}</strong>
              <small>{pedagogy ? `${pedagogy.active_sessions} session(s) active(s)` : 'Donnée indisponible'}</small>
            </article>
            <article className="app-card reports-summary-card">
              <span><AlertTriangle size={17} /> Alertes école</span>
              <strong>{pedagogy || commerce ? alerts : '—'}</strong>
              <small>{commerce ? `${commerce.late_installments} échéance(s) en retard` : 'Vue consolidée'}</small>
            </article>
          </section>

          <section className="reports-layout">
            <article className="app-card reports-executive-card">
              <div className="reports-heading">
                <div>
                  <span className="section-label">Résumé exécutif</span>
                  <h2>État actuel de l’école</h2>
                  <p>Les données ci-dessous sont issues des vues déjà utilisées pour le pilotage de l’école.</p>
                </div>
                <FileText size={22} />
              </div>

              <div className="reports-executive-list">
                <div>
                  <strong>Catalogue</strong>
                  <span>{formations ? `${published} formation(s) publiée(s), ${drafts} à finaliser.` : 'Catalogue indisponible.'}</span>
                </div>
                <div>
                  <strong>Commerce</strong>
                  <span>{commerce ? `${commerce.paid_order_count} commande(s) réglée(s). Reste à encaisser : ${outstanding}.` : 'Données commerciales indisponibles.'}</span>
                </div>
                <div>
                  <strong>Exécution</strong>
                  <span>{pedagogy ? `${pedagogy.active_sessions} session(s) active(s), ${sessionsToWatch.length} à surveiller.` : 'Données de sessions indisponibles.'}</span>
                </div>
                <div>
                  <strong>Attention direction</strong>
                  <span>{alerts > 0 ? `${alerts} signal(aux) nécessitent une vérification.` : 'Aucun signal majeur remonté actuellement.'}</span>
                </div>
              </div>
            </article>

            <aside className="reports-links-stack">
              <Link className="app-card reports-link-card" to="/app/manage/performance">
                <span className="reports-link-icon"><BarChart3 size={20} /></span>
                <div><strong>Statistiques détaillées</strong><small>Charts, tendances et indicateurs de supervision.</small></div>
                <ArrowRight size={17} />
              </Link>
              <Link className="app-card reports-link-card" to="/app/manage/commerce">
                <span className="reports-link-icon"><Banknote size={20} /></span>
                <div><strong>Rapport commercial</strong><small>Commandes, paiements, échéances et encaissements.</small></div>
                <ArrowRight size={17} />
              </Link>
              <Link className="app-card reports-link-card" to="/app/manage/formations">
                <span className="reports-link-icon"><BookOpen size={20} /></span>
                <div><strong>État du catalogue</strong><small>Formations publiées, brouillons et contenu à finaliser.</small></div>
                <ArrowRight size={17} />
              </Link>
              <Link className="app-card reports-link-card" to="/app/manage/pedagogy">
                <span className="reports-link-icon"><CalendarDays size={20} /></span>
                <div><strong>Supervision pédagogique</strong><small>Suivre les sessions sans se substituer aux enseignants.</small></div>
                <ArrowRight size={17} />
              </Link>
            </aside>
          </section>
        </>
      )}
    </main>
  )
}
