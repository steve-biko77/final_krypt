'use client'

import { useEffect, useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { CheckCircle, AlertCircle, XCircle, ArrowUpCircle, FileText } from 'lucide-react'
import { toast } from 'sonner'
import {
  decideAMLReview,
  getAdminAMLDetail,
  requestAMLDocs,
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

interface AMLDecisionPanelProps {
  transferId: string
  onClose: () => void
  onDecided: () => void
}

export default function AMLDecisionPanel({ transferId, onClose, onDecided }: AMLDecisionPanelProps) {
  const router = useRouter()
  const [detail, setDetail] = useState<AdminAMLDetail | null>(null)
  const [motif, setMotif] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()

  useEffect(() => {
    getAdminAMLDetail(transferId)
      .then(setDetail)
      .catch((e) => setError(e instanceof Error ? e.message : 'Chargement impossible.'))
  }, [transferId])

  const handleDecision = (action: 'approve' | 'reject' | 'escalate') => {
    if (action === 'reject' && !motif.trim()) {
      setError('Un motif est requis pour rejeter ce transfert.')
      return
    }
    setError(null)
    startTransition(async () => {
      try {
        await decideAMLReview(transferId, action, motif)
        router.refresh()
        toast.success('Décision enregistrée')
        onDecided()
        onClose()
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Une erreur est survenue.'
        setError(message)
        toast.error('Échec de la décision', { description: message })
      }
    })
  }

  const handleRequestDocs = () => {
    setError(null)
    startTransition(async () => {
      try {
        await requestAMLDocs(transferId)
        router.refresh()
        toast.success('Documents complémentaires demandés')
        onDecided()
        onClose()
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Une erreur est survenue.'
        setError(message)
        toast.error('Échec de la demande', { description: message })
      }
    })
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Revue AML</DialogTitle>
        </DialogHeader>

        {!detail ? (
          <div className="space-y-3 py-2" aria-busy="true" aria-label="Chargement">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-24 w-full rounded-lg" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : (
          <>
            <div className="space-y-3 mb-5">
              <div className="flex justify-between text-14">
                <span className="text-gray-500">Émetteur</span>
                <span className="font-medium text-gray-900">
                  {detail.sender_email ?? '—'}
                  {detail.sender_is_kyc_verified === false && (
                    <Badge variant="warning" className="ml-2">
                      KYC non vérifié
                    </Badge>
                  )}
                </span>
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
                <div className="rounded-lg border border-gray-200 p-3 space-y-2">
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
                  <div className="flex justify-between text-14">
                    <span className="text-gray-500">Résultat OFAC</span>
                    {detail.aml.ofac_match ? (
                      <Badge variant="destructive">Match</Badge>
                    ) : (
                      <Badge variant="secondary">Aucun</Badge>
                    )}
                  </div>
                  <div className="flex justify-between text-14">
                    <span className="text-gray-500">Règles déclenchées</span>
                    <span className="font-medium text-gray-900 text-right">
                      {detail.aml.triggered_rules.length > 0
                        ? detail.aml.triggered_rules.join(', ')
                        : '—'}
                    </span>
                  </div>
                  <div className="flex justify-between text-14">
                    <span className="text-gray-500">Nouveau bénéficiaire</span>
                    <span className="font-medium text-gray-900">
                      {detail.aml.is_new_beneficiary ? 'Oui' : 'Non'}
                    </span>
                  </div>
                  <div className="flex justify-between text-14">
                    <span className="text-gray-500">Transferts (30j)</span>
                    <span className="font-medium text-gray-900">
                      {detail.aml.sender_tx_count_30d}
                    </span>
                  </div>
                </div>
              )}

              {detail.sender_transaction_history.length > 0 && (
                <div>
                  <p className="text-13 font-medium text-gray-700 mb-1">
                    Historique de l&apos;émetteur
                  </p>
                  <div className="max-h-32 overflow-y-auto space-y-1">
                    {detail.sender_transaction_history.map((h) => (
                      <div
                        key={h.transaction_id}
                        className="flex justify-between text-12 text-gray-500"
                      >
                        <span>{h.beneficiary_name} · {h.status}</span>
                        <span>{h.amount_eur} EUR</span>
                      </div>
                    ))}
                  </div>
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
                placeholder="Motif de la décision..."
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-14 text-gray-900 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {error && (
              <p className="text-13 text-red-600 mb-4 flex items-center gap-1">
                <AlertCircle size={14} /> {error}
              </p>
            )}

            <div className="flex gap-2 mb-2">
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
                onClick={() => handleDecision('escalate')}
                disabled={isPending}
                className="flex-1 bg-orange-500 hover:bg-orange-600 text-white"
              >
                <ArrowUpCircle size={16} />
                Escalader
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
            <Button
              type="button"
              onClick={handleRequestDocs}
              disabled={isPending}
              variant="outline"
              className="w-full"
            >
              <FileText size={16} />
              Demander des documents complémentaires
            </Button>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
