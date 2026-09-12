'use client'

import Link from 'next/link'
import { useState } from 'react'
import type { AdminAMLHardBlockedItem } from '@/lib/actions/admin-aml.actions'
import AMLHardBlockDocumentDialog from '@/components/AMLHardBlockDocumentDialog'
import AMLHardBlockFreezeDialog from '@/components/AMLHardBlockFreezeDialog'
import AMLHardBlockTracfinDialog from '@/components/AMLHardBlockTracfinDialog'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'

// Refonte frontend (partie 4b/4) — la liste HARD_BLOCK backend ne renvoie que
// sender_id/pas de montant (voir page.tsx) : ces 3 champs sont enrichis
// côté serveur via le détail générique AML, absents si l'enrichissement a
// échoué pour ce cas précis (ex. transaction introuvable entre-temps).
export interface HardBlockCardItem extends AdminAMLHardBlockedItem {
  amount_eur: string | null
  beneficiary_name: string | null
  sender_email: string | null
}

interface AdminAMLHardBlockClientProps {
  initialData: HardBlockCardItem[]
  initialCount: number
}

function formatEUR(value: string): string {
  const n = parseFloat(value)
  if (isNaN(n)) return value
  return n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function AdminAMLHardBlockClient({
  initialData,
  initialCount,
}: AdminAMLHardBlockClientProps) {
  const [items, setItems] = useState<HardBlockCardItem[]>(initialData)
  const [count] = useState(initialCount)

  // Les 3 actions sont indépendantes (pas un flux séquentiel) : on met juste
  // à jour les badges d'état de la carte concernée après chaque action, sans
  // jamais retirer le cas de la liste (HARD_BLOCK ne change pas de statut).
  const updateItem = (transferId: string, patch: Partial<HardBlockCardItem>) => {
    setItems((prev) =>
      prev.map((i) => (i.transfer_id === transferId ? { ...i, ...patch } : i))
    )
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-24 font-bold text-gray-900">Alertes HARD_BLOCK</h1>
          <p className="text-14 text-gray-500 mt-1">
            {count} cas · match sanctions confirmé, déjà bloqué
          </p>
        </div>
        <Link href="/admin/aml" className="text-13 font-medium text-blue-600 hover:underline">
          ← Retour à la file d&apos;attente
        </Link>
      </div>

      {items.length === 0 ? (
        <div className="flex items-center justify-center py-16 text-gray-400 text-14">
          Aucun cas HARD_BLOCK.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {items.map((item) => (
            <Card key={item.transfer_id}>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <CardTitle className="text-16 truncate">
                      {item.ofac_matched_entry ?? 'Entrée non identifiée'}
                    </CardTitle>
                    <p className="font-mono text-11 text-gray-400 mt-1 truncate">
                      {item.transfer_id}
                    </p>
                  </div>
                  <Badge variant="destructive" className="shrink-0">
                    {item.ofac_similarity !== null
                      ? `${Math.round(item.ofac_similarity * 100)}% similarité`
                      : 'Similarité inconnue'}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="flex flex-col gap-2 text-14">
                <div className="flex justify-between gap-3">
                  <span className="text-gray-500 shrink-0">Émetteur</span>
                  <span className="font-medium text-gray-900 text-right truncate">
                    {item.sender_email ?? item.sender_id}
                  </span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-gray-500 shrink-0">Montant</span>
                  <span className="font-mono font-semibold text-gray-900">
                    {item.amount_eur ? `${formatEUR(item.amount_eur)} EUR` : '—'}
                  </span>
                </div>
                {item.ofac_list && (
                  <div className="flex justify-between gap-3">
                    <span className="text-gray-500 shrink-0">Liste</span>
                    <span className="text-gray-700 text-right">{item.ofac_list}</span>
                  </div>
                )}
                <div className="flex justify-between gap-3">
                  <span className="text-gray-500 shrink-0">Date</span>
                  <span className="text-gray-500">
                    {item.created_at ? new Date(item.created_at).toLocaleDateString('fr-FR') : '—'}
                  </span>
                </div>

                <div className="flex flex-wrap gap-2 pt-2">
                  <Badge variant={item.is_documented ? 'success' : 'secondary'}>
                    {item.is_documented ? 'Documenté' : 'Non documenté'}
                  </Badge>
                  <Badge variant={item.account_frozen ? 'success' : 'secondary'}>
                    {item.account_frozen ? 'Compte gelé' : 'Compte actif'}
                  </Badge>
                  <Badge variant={item.tracfin_report_generated ? 'success' : 'secondary'}>
                    {item.tracfin_report_generated ? 'TRACFIN généré' : 'TRACFIN absent'}
                  </Badge>
                </div>
              </CardContent>

              <CardFooter className="flex flex-wrap gap-2">
                <AMLHardBlockDocumentDialog
                  transferId={item.transfer_id}
                  isDocumented={item.is_documented}
                  onDocumented={() => updateItem(item.transfer_id, { is_documented: true })}
                />
                <AMLHardBlockFreezeDialog
                  transferId={item.transfer_id}
                  senderLabel={item.sender_email ?? item.sender_id}
                  isFrozen={item.account_frozen}
                  onFrozen={() => updateItem(item.transfer_id, { account_frozen: true })}
                />
                <AMLHardBlockTracfinDialog
                  transferId={item.transfer_id}
                  isGenerated={item.tracfin_report_generated}
                  onGenerated={() =>
                    updateItem(item.transfer_id, { tracfin_report_generated: true })
                  }
                />
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
