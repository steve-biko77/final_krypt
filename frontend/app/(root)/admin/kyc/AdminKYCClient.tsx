'use client'

import { useState, useTransition } from 'react'
import { getAdminKYCList, type AdminKYCListItem, type KYCDocumentStatus } from '@/lib/actions/kyc.actions'
import KYCReviewPanel from '@/components/KYCReviewPanel'

const STATUS_LABELS: Record<KYCDocumentStatus, string> = {
  SUBMITTED: 'Soumis',
  ANALYZING: 'En analyse',
  APPROVED: 'Approuvé (auto)',
  APPROVED_MANUAL: 'Approuvé (manuel)',
  PENDING_REVIEW: 'En attente',
  COMPLEMENT_REQUESTED: 'Complément',
  REJECTED: 'Rejeté',
}

const STATUS_COLORS: Record<KYCDocumentStatus, string> = {
  SUBMITTED: 'bg-gray-100 text-gray-700',
  ANALYZING: 'bg-yellow-100 text-yellow-800',
  APPROVED: 'bg-green-100 text-green-800',
  APPROVED_MANUAL: 'bg-green-100 text-green-800',
  PENDING_REVIEW: 'bg-orange-100 text-orange-800',
  COMPLEMENT_REQUESTED: 'bg-blue-100 text-blue-800',
  REJECTED: 'bg-red-100 text-red-800',
}

const DOC_TYPE_LABELS: Record<string, string> = {
  PASSPORT: 'Passeport',
  ID_CARD: "Carte d'identité",
  RESIDENCE_PERMIT: 'Titre de séjour',
  DRIVING_LICENSE: 'Permis de conduire',
}

const ALL_STATUSES: KYCDocumentStatus[] = [
  'SUBMITTED', 'ANALYZING', 'APPROVED', 'APPROVED_MANUAL',
  'PENDING_REVIEW', 'COMPLEMENT_REQUESTED', 'REJECTED',
]

interface AdminKYCClientProps {
  initialData: AdminKYCListItem[]
  initialCount: number
}

export default function AdminKYCClient({ initialData, initialCount }: AdminKYCClientProps) {
  const [documents, setDocuments] = useState<AdminKYCListItem[]>(initialData)
  const [count, setCount] = useState(initialCount)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [selected, setSelected] = useState<AdminKYCListItem | null>(null)
  const [isPending, startTransition] = useTransition()

  const handleFilterChange = (value: string) => {
    setStatusFilter(value)
    startTransition(async () => {
      const data = await getAdminKYCList(value || undefined)
      setDocuments(data.results)
      setCount(data.count)
    })
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-24 font-bold text-gray-900">Dossiers KYC</h1>
          <p className="text-14 text-gray-500 mt-1">{count} dossier{count !== 1 ? 's' : ''}</p>
        </div>

        <select
          value={statusFilter}
          onChange={(e) => handleFilterChange(e.target.value)}
          disabled={isPending}
          className="border border-gray-300 rounded-lg px-3 py-2 text-14 text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        >
          <option value="">Tous les statuts</option>
          {ALL_STATUSES.map((s) => (
            <option key={s} value={s}>{STATUS_LABELS[s]}</option>
          ))}
        </select>
      </div>

      {isPending ? (
        <div className="flex items-center justify-center py-16 text-gray-400 text-14">
          Chargement…
        </div>
      ) : documents.length === 0 ? (
        <div className="flex items-center justify-center py-16 text-gray-400 text-14">
          Aucun dossier trouvé.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-left text-14">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 font-semibold text-gray-600">Utilisateur</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Type</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Statut</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Score IA</th>
                <th className="px-4 py-3 font-semibold text-gray-600">Date</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr
                  key={doc.id}
                  onClick={() => setSelected(doc)}
                  className="border-b border-gray-100 hover:bg-blue-50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900">{doc.user_name}</p>
                    <p className="text-12 text-gray-500">{doc.user_email}</p>
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    {DOC_TYPE_LABELS[doc.document_type] ?? doc.document_type}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-12 font-medium ${STATUS_COLORS[doc.status]}`}>
                      {STATUS_LABELS[doc.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    {doc.analysis_score !== null
                      ? `${Math.round(doc.analysis_score * 100)}%`
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {doc.submitted_at
                      ? new Date(doc.submitted_at).toLocaleDateString('fr-FR')
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <KYCReviewPanel
          document={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  )
}
