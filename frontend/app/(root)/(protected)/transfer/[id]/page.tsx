'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { AlertCircle, ArrowLeft, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import TransferTimeline from '@/components/TransferTimeline'
import {
  cancelTransfer,
  getTransferStatus,
  type TransferStatus,
} from '@/lib/actions/transfer.actions'
import {
  buildTimeline,
  isCancellable,
  isTerminalStatus,
  overallState,
  overallStateLabel,
  type OverallState,
} from '@/lib/transferTimeline'

const POLL_INTERVAL_MS = 5000

function formatEUR(value: string): string {
  const n = parseFloat(value)
  if (isNaN(n)) return value
  return n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatXAF(value: string): string {
  const n = parseFloat(value)
  if (isNaN(n)) return value
  return Math.round(n).toLocaleString('fr-FR')
}

// Refonte frontend (partie 3/4) — mêmes tokens de Badge que JourneyCard
// (components/ui/badge.tsx), pas une palette ad-hoc parallèle.
const OVERALL_BADGE_VARIANT: Record<OverallState, 'success' | 'active' | 'secondary' | 'destructive'> = {
  delivered: 'success',
  in_progress: 'active',
  error: 'destructive',
  cancelled: 'secondary',
}

function OverallBadge({ data }: { data: TransferStatus }) {
  const state = overallState(data.status)
  return <Badge variant={OVERALL_BADGE_VARIANT[state]}>{overallStateLabel(data.status)}</Badge>
}

export default function TransferTrackingPage() {
  const params = useParams<{ id: string }>()
  const id = params?.id

  const [data, setData] = useState<TransferStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [cancelling, setCancelling] = useState(false)
  const [cancelError, setCancelError] = useState<string | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  const fetchStatus = useCallback(async () => {
    if (!id) return
    try {
      const res = await getTransferStatus(id)
      setData(res)
      setError(null)
      // Statut terminal → on cesse de solliciter le backend.
      if (isTerminalStatus(res.status)) stopPolling()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur de chargement')
    } finally {
      setLoading(false)
    }
  }, [id, stopPolling])

  useEffect(() => {
    if (!id) return
    fetchStatus()
    intervalRef.current = setInterval(fetchStatus, POLL_INTERVAL_MS)
    return stopPolling
  }, [id, fetchStatus, stopPolling])

  const handleCancel = useCallback(async () => {
    if (!id) return

    setCancelling(true)
    setCancelError(null)
    try {
      const result = await cancelTransfer(id)
      // Mise à jour immédiate de l'affichage — pas besoin d'attendre le
      // prochain cycle de polling (KRYP-28).
      setData((prev) => (prev ? { ...prev, status: result.status } : prev))
      stopPolling()
      setConfirmOpen(false)
      toast.success('Transfert annulé')
    } catch (e) {
      const message = e instanceof Error ? e.message : "Échec de l'annulation"
      setCancelError(message)
      toast.error("Échec de l'annulation", { description: message })
    } finally {
      setCancelling(false)
    }
  }, [id, stopPolling])

  if (loading) {
    return (
      <div className="w-full max-w-xl p-4 sm:p-8" aria-busy="true" aria-label="Chargement du suivi">
        <div className="rounded-2xl border border-gray-200 bg-white p-4 sm:p-5 mb-8 shadow-form">
          <div className="flex items-center justify-between gap-3 mb-3">
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
          <Skeleton className="h-4 w-48 mb-2" />
          <Skeleton className="h-3 w-32" />
        </div>
        <div className="flex flex-col gap-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex gap-4">
              <Skeleton className="size-9 rounded-full shrink-0" />
              <div className="flex-1 rounded-xl border border-gray-200 p-4">
                <Skeleton className="h-4 w-32 mb-2" />
                <Skeleton className="h-3 w-full max-w-64" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="p-4 sm:p-8">
        <div className="flex items-start gap-2 p-4 rounded-xl bg-red-50 border border-red-200 max-w-xl">
          <AlertCircle size={18} className="text-red-500 mt-0.5 shrink-0" aria-hidden="true" />
          <div>
            <p className="text-14 font-semibold text-red-700">Suivi indisponible</p>
            <p className="text-13 text-red-700 mt-1">{error}</p>
            <Link
              href="/transfer"
              className="inline-flex items-center gap-1 mt-3 text-13 font-medium text-blue-600 hover:underline max-md:min-h-11"
            >
              <ArrowLeft size={14} /> Retour aux transferts
            </Link>
          </div>
        </div>
      </div>
    )
  }

  if (!data) return null

  const steps = buildTimeline({
    status: data.status,
    beneficiaryName: data.beneficiary_name,
    operator: data.operator,
    escrowTxHash: data.escrow_tx_hash,
    payoutReference: data.payout_reference,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
    escrowedAt: data.escrowed_at,
    batchTxHash: data.batch_tx_hash,
    batchId: data.batch_id,
  })

  return (
    <div className="w-full max-w-xl p-4 sm:p-8">
      {/* En-tête récapitulatif — montant en police mono (point 3, partie 3/4) */}
      <div className="rounded-2xl border border-gray-200 bg-white p-4 sm:p-5 mb-8 shadow-form">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-3">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-24 md:text-18 tabular-nums font-bold text-gray-900">
            <span>{formatEUR(data.amount_eur)} €</span>
            <ArrowRight size={16} className="text-gray-400" aria-hidden="true" />
            <span>{formatXAF(data.amount_xaf)} FCFA</span>
          </div>
          <OverallBadge data={data} />
        </div>
        <p className="text-14 font-semibold text-gray-800">
          {data.beneficiary_name}
          <span className="text-13 font-normal text-gray-500"> · {data.beneficiary_country}</span>
        </p>
        <p className="text-12 font-mono text-gray-400 mt-1">Réf. {data.transaction_id}</p>

        {isCancellable(data.status) && (
          <div className="mt-4">
            <Button
              type="button"
              onClick={() => setConfirmOpen(true)}
              disabled={cancelling}
              variant="outline"
              size="sm"
              className="text-red-600 border-red-200 hover:bg-red-50 max-md:h-11 max-md:px-4"
            >
              {cancelling ? 'Annulation…' : 'Annuler le transfert'}
            </Button>
            {cancelError && (
              <p className="text-12 text-red-600 mt-1">{cancelError}</p>
            )}
          </div>
        )}
      </div>

      {/* Timeline */}
      <TransferTimeline steps={steps} />

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Annuler ce transfert ?</DialogTitle>
            <DialogDescription>
              Cette action est irréversible. Le transfert ne sera pas envoyé et vous ne pourrez
              pas revenir en arrière.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmOpen(false)}
              disabled={cancelling}
              className="max-md:h-11"
            >
              Retour
            </Button>
            <Button
              type="button"
              onClick={handleCancel}
              disabled={cancelling}
              className="bg-red-600 hover:bg-red-700 text-white max-md:h-11"
            >
              {cancelling ? 'Annulation…' : 'Confirmer l’annulation'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
