'use client'

import { useEffect, useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { CheckCircle, AlertCircle, XCircle, X } from 'lucide-react'
import {
  decideAMLEscalatedReview,
  getAdminAMLEscalatedDetail,
  type AdminAMLDetail,
} from '@/lib/actions/admin-aml.actions'

interface AMLEscalatedDecisionPanelProps {
  transferId: string
  onClose: () => void
  onDecided: () => void
}

export default function AMLEscalatedDecisionPanel({
  transferId,
  onClose,
  onDecided,
}: AMLEscalatedDecisionPanelProps) {
  const router = useRouter()
  const [detail, setDetail] = useState<AdminAMLDetail | null>(null)
  const [motif, setMotif] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()

  useEffect(() => {
    getAdminAMLEscalatedDetail(transferId)
      .then(setDetail)
      .catch((e) => setError(e instanceof Error ? e.message : 'Chargement impossible.'))
  }, [transferId])

  // KRYP-31 — SEULEMENT approve/reject à ce niveau, jamais de ré-escalade
  // (Fig. 10 point 5) : pas de troisième bouton "Escalader" ici.
  const handleDecision = (action: 'approve' | 'reject') => {
    if (action === 'reject' && !motif.trim()) {
      setError('Un motif est requis pour rejeter ce transfert.')
      return
    }
    setError(null)
    startTransition(async () => {
      try {
        await decideAMLEscalatedReview(transferId, action, motif)
        router.refresh()
        onDecided()
        onClose()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Une erreur est survenue.')
      }
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 p-6 relative max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
          aria-label="Fermer"
        >
          <X size={20} />
        </button>

        <h2 className="text-18 font-bold text-gray-900 mb-4">Revue escaladée — décision finale</h2>

        {!detail ? (
          <p className="text-14 text-gray-400 py-8 text-center">Chargement…</p>
        ) : (
          <>
            {detail.escalation_comment && (
              <div className="mb-4 rounded-lg border border-orange-200 bg-orange-50 p-3">
                <p className="text-12 font-medium text-orange-800 mb-1">
                  Commentaire du premier niveau
                </p>
                <p className="text-13 text-orange-900">{detail.escalation_comment}</p>
              </div>
            )}

            <div className="space-y-3 mb-5">
              <div className="flex justify-between text-14">
                <span className="text-gray-500">Émetteur</span>
                <span className="font-medium text-gray-900">{detail.sender_email ?? '—'}</span>
              </div>
              <div className="flex justify-between text-14">
                <span className="text-gray-500">Bénéficiaire</span>
                <span className="font-medium text-gray-900">
                  {detail.beneficiary_name} ({detail.beneficiary_country})
                </span>
              </div>
              <div className="flex justify-between text-14">
                <span className="text-gray-500">Montant</span>
                <span className="font-medium text-gray-900">{detail.amount_eur} EUR</span>
              </div>
              {detail.aml && (
                <div className="flex justify-between text-14">
                  <span className="text-gray-500">
                    Score tag ML
                    <span className="block text-11 text-gray-400">
                      {detail.aml.tag_ml_score_label}
                    </span>
                  </span>
                  <span className="font-medium text-gray-900">
                    {Math.round(detail.aml.tag_ml_score * 100)}%
                  </span>
                </div>
              )}
            </div>

            <div className="mb-5">
              <label className="block text-14 font-medium text-gray-700 mb-1">
                Motif / commentaire
                <span className="text-red-500 ml-1 text-12">(requis pour rejet)</span>
                <span className="block text-11 text-gray-400 font-normal mt-0.5">
                  Usage strictement interne — jamais transmis à l&apos;utilisateur.
                </span>
              </label>
              <textarea
                value={motif}
                onChange={(e) => setMotif(e.target.value)}
                rows={3}
                placeholder="Motif de la décision finale..."
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-14 text-gray-900 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {error && (
              <p className="text-13 text-red-600 mb-4 flex items-center gap-1">
                <AlertCircle size={14} /> {error}
              </p>
            )}

            <div className="flex gap-2">
              <button
                onClick={() => handleDecision('approve')}
                disabled={isPending}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-green-600 text-white text-14 font-semibold hover:bg-green-700 disabled:opacity-50 transition"
              >
                <CheckCircle size={16} />
                Approuver
              </button>
              <button
                onClick={() => handleDecision('reject')}
                disabled={isPending}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-red-600 text-white text-14 font-semibold hover:bg-red-700 disabled:opacity-50 transition"
              >
                <XCircle size={16} />
                Rejeter
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
