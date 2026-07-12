import { redirect } from 'next/navigation'
import { getLoggedInUser } from '@/lib/actions/user.actions'
import { getAdminAMLEscalated } from '@/lib/actions/admin-aml.actions'
import AdminAMLEscalatedClient from './AdminAMLEscalatedClient'

export default async function AdminAMLEscalatedPage() {
  const user = await getLoggedInUser()

  if (!user || !user.is_staff || !user.is_2fa_enabled) {
    redirect('/')
  }

  const data = await getAdminAMLEscalated()

  return (
    <div className="flex flex-col gap-8 p-8 max-w-6xl">
      <AdminAMLEscalatedClient initialData={data.results} initialCount={data.count} />
    </div>
  )
}
