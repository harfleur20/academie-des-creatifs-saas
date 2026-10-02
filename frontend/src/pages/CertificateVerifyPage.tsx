import { useEffect, useState } from 'react'
import { CheckCircle2, ShieldCheck, XCircle } from 'lucide-react'
import { useParams } from 'react-router-dom'
import {
  ApiError,
  verifyCertificate,
  type CertificateInfo,
} from '../lib/api'

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

  return (
    <main className="certificate-verify-page">
      <section className="certificate-verify-card">
        <div className="certificate-verify-icon">
          {certificate ? <ShieldCheck size={30} /> : error ? <XCircle size={30} /> : <CheckCircle2 size={30} />}
        </div>
        {certificate ? (
          <>
            <span className="section-label">Certificat vérifié</span>
            <h1>{certificate.formation_title}</h1>
            <p>Attribué à <strong>{certificate.student_name}</strong></p>
            <dl>
              <div><dt>Numéro</dt><dd>{certificate.certificate_number}</dd></div>
              <div><dt>Date d’émission</dt><dd>{new Date(certificate.issued_at).toLocaleDateString('fr-FR')}</dd></div>
              <div><dt>Statut</dt><dd>Valide</dd></div>
            </dl>
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
