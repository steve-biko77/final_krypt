import { redirect } from 'next/navigation'
import { getLoggedInUser } from '@/lib/actions/user.actions'
import AdminDashboardClient from './AdminDashboardClient'

export default async function AdminDashboardPage() {
  const user = await getLoggedInUser()

  // Même gate que le reste de la console (IsStaffWith2FA côté backend) —
  // cf. app/(root)/page.tsx pour la redirection post-connexion vers cette
  // page.
  if (!user || !user.is_staff || !user.is_2fa_enabled) {
    redirect('/')
  }

  return (
    <div className="flex flex-col gap-8 p-4 sm:p-8 max-w-6xl">
      <AdminDashboardClient />
    </div>
  )
}
