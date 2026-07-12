import { redirect } from 'next/navigation'
import { getLoggedInUser } from '@/lib/actions/user.actions'
import { getAdminAMLDailyReport } from '@/lib/actions/admin-aml.actions'
import AdminAMLDailyReportClient from './AdminAMLDailyReportClient'

export default async function AdminAMLDailyReportPage() {
  const user = await getLoggedInUser()

  if (!user || !user.is_staff || !user.is_2fa_enabled) {
    redirect('/')
  }

  const report = await getAdminAMLDailyReport()

  return (
    <div className="flex flex-col gap-8 p-8 max-w-4xl">
      <AdminAMLDailyReportClient initialReport={report} />
    </div>
  )
}
