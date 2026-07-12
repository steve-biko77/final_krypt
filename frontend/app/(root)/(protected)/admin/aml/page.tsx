import { redirect } from 'next/navigation'
import { getLoggedInUser } from '@/lib/actions/user.actions'
import { getAdminAMLPending } from '@/lib/actions/admin-aml.actions'
import AdminAMLClient from './AdminAMLClient'

export default async function AdminAMLPage() {
  const user = await getLoggedInUser()

  // KRYP-31 — is_staff ET 2FA activée (Fig. 10 : porte d'entrée du dashboard
  // compliance). Le backend impose déjà le même gate (IsStaffWith2FA) ; cette
  // vérification côté page évite un aller-retour 403 inutile.
  if (!user || !user.is_staff || !user.is_2fa_enabled) {
    redirect('/')
  }

  const data = await getAdminAMLPending()

  return (
    <div className="flex flex-col gap-8 p-8 max-w-6xl">
      <AdminAMLClient initialData={data.results} initialCount={data.count} />
    </div>
  )
}
