import { useState } from 'react'
import { Copy } from 'lucide-react'
import { useTenant } from '../app/TenantContext'

export function InvitationLink({ token }: { token: string }) {
  const { activeOrganization } = useTenant()
  const [message, setMessage] = useState('')
  // The school's own address when it has one: the invitee lands on the school, not the platform.
  const origin = activeOrganization?.public_site_url || window.location.origin
  const url = new URL(`/invite/${encodeURIComponent(token)}`, origin).toString()

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
      setMessage('Lien copié.')
    } catch {
      setMessage('Sélectionnez le lien pour le copier.')
    }
  }

  return <div className="invitation-link">
    <label>Lien d’invitation<input value={url} readOnly onFocus={(event) => event.currentTarget.select()} /></label>
    <button className="secondary-button" type="button" onClick={() => void copy()} aria-label="Copier le lien d’invitation"><Copy size={15} /> Copier</button>
    {message && <small role="status">{message}</small>}
  </div>
}
