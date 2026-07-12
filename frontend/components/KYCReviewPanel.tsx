'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { CheckCircle, AlertCircle, XCircle, X } from 'lucide-react'
import { reviewKYCDocument, type AdminKYCListItem } from '@/lib/actions/kyc.actions'

interface KYCReviewPanelProps {
  document: AdminKYCListItem
  onClose: () => void
}

const STATUS_LABELS: Record<string, string> = {
  SUBMITTED: 'Soumis',
  ANALYZING: 'En analyse',
  APPROVED: 'Approuvé (auto)',
  APPROVED_MANUAL: 'Approuvé (manuel)',
  PENDING_REVIEW: 'En attente de révision',
  COMPLEMENT_REQUESTED: 'Complément demandé',
  REJECTED: 'Rejeté',
}

const DOC_TYPE_LABELS: Record<string, string> = {
  PASSPORT: 'Passeport',
  ID_CARD: 'Carte d\'identité',
  RESIDENCE_PERMIT: 'Titre de séjour',
  DRIVING_LICENSE: 'Permis de conduire',
}

const KYCReviewPanel = ({ document: doc, onClose }: KYCReviewPanelProps) => {
  const router = useRouter()
  const [comment, setComment] = useState(doc.review_comment ?? '')
  const [error, setError] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()

  const scorePercent = doc.analysis_score !== null
    ? Math.round(doc.analysis_score * 100)
    : null

  const scoreColor =
    scorePercent === null ? 'bg-gray-300'
    : scorePercent >= 80 ? 'bg-green-500'
    : scorePercent >= 50 ? 'bg-yellow-500'
    : 'bg-red-500'

  const handleDecision = (decision: 'APPROVED' | 'COMPLEMENT_REQUESTED' | 'REJECTED') => {
    if (decision === 'REJECTED' && !comment.trim()) {
      setError('Un commentaire est requis pour rejeter un dossier.')
      return
    }
    setError(null)
    startTransition(async () => {
      try {
        await reviewKYCDocument(doc.id, decision, comment)
        router.refresh()
        onClose()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Une erreur est survenue.')
      }
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
          aria-label="Fermer"
        >
          <X size={20} />
        </button>

        <h2 className="text-18 font-bold text-gray-900 mb-4">Révision du dossier KYC</h2>

        <div className="space-y-3 mb-5">
          <div className="flex justify-between text-14">
            <span className="text-gray-500">Utilisateur</span>
            <span className="font-medium text-gray-900">{doc.user_name} — {doc.user_email}</span>
          </div>
          <div className="flex justify-between text-14">
            <span className="text-gray-500">Type de document</span>
            <span className="font-medium text-gray-900">
              {DOC_TYPE_LABELS[doc.document_type] ?? doc.document_type}
            </span>
          </div>
          <div className="flex justify-between text-14">
            <span className="text-gray-500">Statut actuel</span>
            <span className="font-medium text-gray-900">{STATUS_LABELS[doc.status] ?? doc.status}</span>
          </div>
          <div className="flex justify-between text-14">
            <span className="text-gray-500">Soumis le</span>
            <span className="font-medium text-gray-900">
              {doc.submitted_at ? new Date(doc.submitted_at).toLocaleDateString('fr-FR') : '—'}
            </span>
          </div>

          {scorePercent !== null && (
            <div className="text-14">
              <div className="flex justify-between mb-1">
                <span className="text-gray-500">Score IA</span>
                <span className="font-medium text-gray-900">{scorePercent}%</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${scoreColor}`}
                  style={{ width: `${scorePercent}%` }}
                />
              </div>
            </div>
          )}
        </div>

        <div className="mb-5">
          <label className="block text-14 font-medium text-gray-700 mb-1">
            Commentaire admin
            <span className="text-red-500 ml-1 text-12">(requis pour rejet)</span>
          </label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
            placeholder="Motif de la décision..."
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
            onClick={() => handleDecision('APPROVED')}
            disabled={isPending}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-green-600 text-white text-14 font-semibold hover:bg-green-700 disabled:opacity-50 transition"
          >
            <CheckCircle size={16} />
            Approuver
          </button>
          <button
            onClick={() => handleDecision('COMPLEMENT_REQUESTED')}
            disabled={isPending}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-orange-500 text-white text-14 font-semibold hover:bg-orange-600 disabled:opacity-50 transition"
          >
            <AlertCircle size={16} />
            Complément
          </button>
          <button
            onClick={() => handleDecision('REJECTED')}
            disabled={isPending}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-red-600 text-white text-14 font-semibold hover:bg-red-700 disabled:opacity-50 transition"
          >
            <XCircle size={16} />
            Rejeter
          </button>
        </div>
      </div>
    </div>
  )
}

export default KYCReviewPanel
