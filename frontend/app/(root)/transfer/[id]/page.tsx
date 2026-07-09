'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { AlertCircle, ArrowLeft, ArrowRight } from 'lucide-react'

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

function OverallBadge({ data }: { data: TransferStatus }) {
  const state = overallState(data.status)
  const label = overallStateLabel(data.status)
  const cls =
    state === 'delivered'
      ? 'bg-green-100 text-green-700'
      : state === 'cancelled'
        ? 'bg-gray-100 text-gray-600'
        : state === 'error'
          ? 'bg-red-100 text-red-700'
          : 'bg-blue-100 text-blue-700'
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-12 font-semibold ${cls}`}>
      {label}
    </span>
  )
}

export default function TransferTrackingPage() {
  const params = useParams<{ id: string }>()
  const id = params?.id

  const [data, setData] = useState<TransferStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [cancelling, setCancelling] = useState(false)
  const [cancelError, setCancelError] = useState<string | null>(null)
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
    const confirmed = window.confirm(
      'Annuler ce transfert ? Cette action est irréversible.',
    )
    if (!confirmed) return

    setCancelling(true)
    setCancelError(null)
    try {
      const result = await cancelTransfer(id)
      // Mise à jour immédiate de l'affichage — pas besoin d'attendre le
      // prochain cycle de polling (KRYP-28).
      setData((prev) => (prev ? { ...prev, status: result.status } : prev))
      stopPolling()
    } catch (e) {
      setCancelError(e instanceof Error ? e.message : "Échec de l'annulation")
    } finally {
      setCancelling(false)
    }
  }, [id, stopPolling])

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-14 text-gray-400 py-10">
        <span className="animate-spin inline-block w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full" />
        Chargement du suivi…
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="flex items-start gap-2 p-4 rounded-lg bg-red-50 border border-red-200 max-w-xl">
        <AlertCircle size={18} className="text-red-500 mt-0.5 shrink-0" />
        <div>
          <p className="text-14 font-semibold text-red-700">Suivi indisponible</p>
          <p className="text-13 text-red-700 mt-1">{error}</p>
          <Link
            href="/transfer"
            className="inline-flex items-center gap-1 mt-3 text-13 font-medium text-blue-600 hover:underline"
          >
            <ArrowLeft size={14} /> Retour aux transferts
          </Link>
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
    <div className="w-full max-w-xl">
      {/* En-tête récapitulatif */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 mb-8">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2 text-18 font-bold text-gray-900 font-mono">
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
        <p className="text-12 text-gray-400 font-mono mt-1">Réf. {data.transaction_id}</p>

        {isCancellable(data.status) && (
          <div className="mt-4">
            <button
              type="button"
              onClick={handleCancel}
              disabled={cancelling}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-13 font-medium text-red-600 border border-red-200 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-1"
            >
              {cancelling ? 'Annulation…' : 'Annuler le transfert'}
            </button>
            {cancelError && (
              <p className="text-12 text-red-600 mt-1">{cancelError}</p>
            )}
          </div>
        )}
      </div>

      {/* Timeline */}
      <TransferTimeline steps={steps} />
    </div>
  )
}
