import { redirect } from 'next/navigation'
import { getLoggedInUser } from '@/lib/actions/user.actions'
import { getAdminAMLDetail, getAdminAMLHardBlocked } from '@/lib/actions/admin-aml.actions'
import AdminAMLHardBlockClient, { type HardBlockCardItem } from './AdminAMLHardBlockClient'

export default async function AdminAMLHardBlockPage() {
  const user = await getLoggedInUser()

  if (!user || !user.is_staff || !user.is_2fa_enabled) {
    redirect('/')
  }

  const data = await getAdminAMLHardBlocked()

  // Refonte frontend (partie 4b/4) — la liste HARD_BLOCK ne renvoie que
  // l'ID brut de l'émetteur, aucun montant (admin_hard_block_views.py).
  // Le détail générique (/api/admin/aml/{id}) n'impose aucun filtre de
  // statut AML (contrairement à /decide) : on l'utilise pour enrichir
  // chaque carte plutôt que d'exposer un nouvel endpoint backend.
  const items: HardBlockCardItem[] = await Promise.all(
    data.results.map(async (item) => {
      try {
        const detail = await getAdminAMLDetail(item.transfer_id)
        return {
          ...item,
          amount_eur: detail.amount_eur,
          beneficiary_name: detail.beneficiary_name,
          sender_email: detail.sender_email,
        }
      } catch {
        return { ...item, amount_eur: null, beneficiary_name: null, sender_email: null }
      }
    })
  )

  return (
    <div className="flex flex-col gap-8 p-4 sm:p-8 max-w-6xl">
      <AdminAMLHardBlockClient initialData={items} initialCount={data.count} />
    </div>
  )
}
