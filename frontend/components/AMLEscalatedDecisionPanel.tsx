'use client'

import { useEffect, useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { CheckCircle, AlertCircle, XCircle } from 'lucide-react'
import { toast } from 'sonner'
import {
  decideAMLEscalatedReview,
  getAdminAMLEscalatedDetail,
  type AdminAMLDetail,
} from '@/lib/actions/admin-aml.actions'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

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
        toast.success('Décision finale enregistrée')
        onDecided()
        onClose()
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Une erreur est survenue.'
        setError(message)
        toast.error('Échec de la décision', { description: message })
      }
    })
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Revue escaladée — décision finale</DialogTitle>
        </DialogHeader>

        {!detail ? (
          <div className="space-y-3 py-2" aria-busy="true" aria-label="Chargement">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-16 w-full rounded-lg" />
          </div>
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
                  <Badge variant="secondary">{Math.round(detail.aml.tag_ml_score * 100)}%</Badge>
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
              <Button
                type="button"
                onClick={() => handleDecision('approve')}
                disabled={isPending}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white"
              >
                <CheckCircle size={16} />
                Approuver
              </Button>
              <Button
                type="button"
                onClick={() => handleDecision('reject')}
                disabled={isPending}
                variant="destructive"
                className="flex-1"
              >
                <XCircle size={16} />
                Rejeter
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
