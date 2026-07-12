'use client'

import Link from 'next/link'
import { useState } from 'react'
import type { AdminAMLPendingItem } from '@/lib/actions/admin-aml.actions'
import AMLEscalatedDecisionPanel from '@/components/AMLEscalatedDecisionPanel'

interface AdminAMLEscalatedClientProps {
  initialData: AdminAMLPendingItem[]
  initialCount: number
}

export default function AdminAMLEscalatedClient({
  initialData,
  initialCount,
}: AdminAMLEscalatedClientProps) {
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
          <h1 className="text-24 font-bold text-gray-900">Revue AML — Escaladés</h1>
          <p className="text-14 text-gray-500 mt-1">
            {count} dossier{count !== 1 ? 's' : ''} en revue de second niveau
          </p>
        </div>
        <Link href="/admin/aml" className="text-13 font-medium text-blue-600 hover:underline">
          ← Retour à la file d&apos;attente
        </Link>
      </div>

      {items.length === 0 ? (
        <div className="flex items-center justify-center py-16 text-gray-400 text-14">
          Aucun dossier escaladé.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-left text-14">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 font-semibold text-gray-600">Référence</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Score (priorité)</th>
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
        <AMLEscalatedDecisionPanel
          transferId={selected.transfer_id}
          onClose={() => setSelected(null)}
          onDecided={() => removeFromList(selected.transfer_id)}
        />
      )}
    </div>
  )
}
