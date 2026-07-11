'use client'

import Link from 'next/link'
import { useState } from 'react'
import type { AdminAMLPendingItem } from '@/lib/actions/admin-aml.actions'
import AMLDecisionPanel from '@/components/AMLDecisionPanel'

interface AdminAMLClientProps {
  initialData: AdminAMLPendingItem[]
  initialCount: number
}

export default function AdminAMLClient({ initialData, initialCount }: AdminAMLClientProps) {
  const [items, setItems] = useState<AdminAMLPendingItem[]>(initialData)
  const [count, setCount] = useState(initialCount)
  const [selected, setSelected] = useState<AdminAMLPendingItem | null>(null)

  const removeFromList = (transferId: string) => {
    setItems((prev) => prev.filter((i) => i.transfer_id !== transferId))
    setCount((c) => Math.max(0, c - 1))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-24 font-bold text-gray-900">Revue AML — En attente</h1>
          {/* Priorisation par score tag ML DÉCROISSANT (seuils_production.md §2,
              Couche 3) : trie l'AFFICHAGE, jamais un critère de décision. */}
          <p className="text-14 text-gray-500 mt-1">
            {count} transfert{count !== 1 ? 's' : ''} · trié par signal de priorité décroissant
          </p>
        </div>
        <div className="flex gap-4">
          <Link
            href="/admin/aml/escalated"
            className="text-13 font-medium text-blue-600 hover:underline"
          >
            Voir les dossiers escaladés →
          </Link>
          <Link
            href="/admin/aml/hard-block"
            className="text-13 font-medium text-red-600 hover:underline"
          >
            Voir les alertes HARD_BLOCK →
          </Link>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="flex items-center justify-center py-16 text-gray-400 text-14">
          Aucun transfert en attente de revue.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-left text-14">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 font-semibold text-gray-600">Référence</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Score (priorité)</th>
                <th className="px-4 py-3 font-semibold text-gray-600">OFAC</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Règles déclenchées</th>
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
                    {Math.round(item.tag_ml_score * 100)}%
                  </td>
                  <td className="px-4 py-3">
                    {item.ofac_match ? (
                      <span className="px-2 py-1 rounded-full text-12 font-medium bg-red-100 text-red-800">
                        Match
                      </span>
                    ) : (
                      <span className="px-2 py-1 rounded-full text-12 font-medium bg-gray-100 text-gray-600">
                        —
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    {item.triggered_rules.length > 0 ? item.triggered_rules.join(', ') : '—'}
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
        <AMLDecisionPanel
          transferId={selected.transfer_id}
          onClose={() => setSelected(null)}
          onDecided={() => removeFromList(selected.transfer_id)}
        />
      )}
    </div>
  )
}
