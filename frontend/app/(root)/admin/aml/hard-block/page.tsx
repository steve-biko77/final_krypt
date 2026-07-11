import { redirect } from 'next/navigation'
import { getLoggedInUser } from '@/lib/actions/user.actions'
import { getAdminAMLHardBlocked } from '@/lib/actions/admin-aml.actions'
import AdminAMLHardBlockClient from './AdminAMLHardBlockClient'

export default async function AdminAMLHardBlockPage() {
  const user = await getLoggedInUser()

  if (!user || !user.is_staff || !user.is_2fa_enabled) {
    redirect('/')
  }

  const data = await getAdminAMLHardBlocked()

  return (
    <div className="flex flex-col gap-8 p-8 max-w-6xl">
      <AdminAMLHardBlockClient initialData={data.results} initialCount={data.count} />
    </div>
  )
}
