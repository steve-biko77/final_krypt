'use client'

import Link from 'next/link'
import { useState } from 'react'
import type { AdminAMLHardBlockedItem } from '@/lib/actions/admin-aml.actions'
import AMLHardBlockPanel from '@/components/AMLHardBlockPanel'

interface AdminAMLHardBlockClientProps {
  initialData: AdminAMLHardBlockedItem[]
  initialCount: number
}

function StatusPill({ done, label }: { done: boolean; label: string }) {
  return (
    <span
      className={`px-2 py-1 rounded-full text-11 font-medium ${
        done ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-500'
      }`}
    >
      {label}
    </span>
  )
}

export default function AdminAMLHardBlockClient({
  initialData,
  initialCount,
}: AdminAMLHardBlockClientProps) {
  const [items, setItems] = useState<AdminAMLHardBlockedItem[]>(initialData)
  const [count] = useState(initialCount)
  const [selected, setSelected] = useState<AdminAMLHardBlockedItem | null>(null)

  // Les 3 actions sont indépendantes (pas un flux séquentiel) : on met juste
  // à jour les pastilles de statut de la ligne concernée après chaque action,
  // sans jamais retirer le cas de la liste (HARD_BLOCK ne change pas).
  const updateItem = (transferId: string, patch: Partial<AdminAMLHardBlockedItem>) => {
    setItems((prev) =>
      prev.map((i) => (i.transfer_id === transferId ? { ...i, ...patch } : i))
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
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
        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-left text-14">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 font-semibold text-gray-600">Référence</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Entrée sanctionnée</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Similarité</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Statut dossier</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Date</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.transfer_id}
                  onClick={() => setSelected(item)}
                  className="border-b border-gray-100 hover:bg-blue-50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-12 text-gray-700">
                    {item.transfer_id}
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    {item.ofac_matched_entry ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    {item.ofac_similarity !== null
                      ? `${Math.round(item.ofac_similarity * 100)}%`
                      : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1 flex-wrap">
                      <StatusPill done={item.is_documented} label="Documenté" />
                      <StatusPill done={item.account_frozen} label="Compte gelé" />
                      <StatusPill done={item.tracfin_report_generated} label="TRACFIN" />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {item.created_at ? new Date(item.created_at).toLocaleDateString('fr-FR') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <AMLHardBlockPanel
          item={selected}
          onClose={() => setSelected(null)}
          onUpdated={(patch) => updateItem(selected.transfer_id, patch)}
        />
      )}
    </div>
  )
}
