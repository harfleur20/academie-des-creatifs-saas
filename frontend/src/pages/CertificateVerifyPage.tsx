import { activeSchoolLocale } from '../app/schoolLocale'
import { useEffect, useState, type CSSProperties } from 'react'
import {
  CheckCircle2,
  Download,
  ShieldCheck,
  XCircle,
} from 'lucide-react'
import { useParams } from 'react-router-dom'
import {
  ApiError,
  downloadVerifiedCertificatePdf,
  verifyCertificate,
  type CertificateInfo,
} from '../lib/api'
import { saveBlobFile } from '../lib/download'

export function CertificateVerifyPage() {
  const { token } = useParams()
  const [certificate, setCertificate] = useState<CertificateInfo | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) {
      setError('Certificat introuvable.')
      return
    }
    verifyCertificate(token)
      .then(setCertificate)
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : 'Impossible de vérifier ce certificat.',
        ),
      )
  }, [token])

  async function download() {
    if (!certificate || !token) return
    try {
      const blob = await downloadVerifiedCertificatePdf(token)
      saveBlobFile(blob, certificate.certificate_number + '.pdf')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Téléchargement impossible.')
    }
  }

  const brandStyle = certificate?.primary_color
    ? ({
        '--certificate-brand': certificate.primary_color,
      } as CSSProperties)
    : undefined

  return (
    <main className="certificate-verify-page" style={brandStyle}>
      <section className="certificate-verify-card">
        <div className="certificate-verify-icon">
          {certificate ? (
            <ShieldCheck size={30} />
          ) : error ? (
            <XCircle size={30} />
          ) : (
            <CheckCircle2 size={30} />
          )}
        </div>

        {certificate ? (
          <>
            {certificate.logo_url && (
              <img
                className="certificate-school-logo"
                src={certificate.logo_url}
                alt={certificate.school_name || 'École'}
              />
            )}
            <span className="section-label">Certificat vérifié</span>
            {certificate.school_name && (
              <strong className="certificate-school-name">
                {certificate.school_name}
              </strong>
            )}
            <h1>{certificate.formation_title}</h1>
            <p>
              Attribué à <strong>{certificate.student_name}</strong>
            </p>
            <dl>
              <div>
                <dt>Numéro</dt>
                <dd>{certificate.certificate_number}</dd>
              </div>
              {certificate.student_code && (
                <div>
                  <dt>Matricule</dt>
                  <dd>{certificate.student_code}</dd>
                </div>
              )}
              {certificate.session_label && (
                <div>
                  <dt>Session</dt>
                  <dd>{certificate.session_label}</dd>
                </div>
              )}
              <div>
                <dt>Date d’émission</dt>
                <dd>
                  {new Date(certificate.issued_at).toLocaleDateString(activeSchoolLocale())}
                </dd>
              </div>
              <div>
                <dt>Statut</dt>
                <dd>Valide</dd>
              </div>
            </dl>
            <button
              className="certificate-public-download"
              type="button"
              onClick={() => void download()}
            >
              <Download size={14} />
              Télécharger le certificat PDF
            </button>
          </>
        ) : error ? (
          <>
            <span className="section-label">Vérification impossible</span>
            <h1>Certificat non valide</h1>
            <p>{error}</p>
          </>
        ) : (
          <>
            <span className="section-label">Vérification</span>
            <h1>Contrôle du certificat…</h1>
          </>
        )}
      </section>
    </main>
  )
}
