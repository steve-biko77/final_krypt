import { redirect } from 'next/navigation'
import { getLoggedInUser } from '@/lib/actions/user.actions'
import { getAdminKYCList } from '@/lib/actions/kyc.actions'
import AdminKYCClient from './AdminKYCClient'

export default async function AdminKYCPage() {
  const user = await getLoggedInUser()

  if (!user || !user.is_staff) {
    redirect('/')
  }

  const data = await getAdminKYCList()

  return (
    <div className="flex flex-col gap-8 p-8 max-w-6xl">
      <AdminKYCClient initialData={data.results} initialCount={data.count} />
    </div>
  )
}
