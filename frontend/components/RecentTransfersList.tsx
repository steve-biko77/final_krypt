'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { AlertCircle, ArrowRight } from 'lucide-react'
import { motion, useReducedMotion } from 'framer-motion'
import JourneyCard, { type JourneyCardStatus } from '@/components/JourneyCard'
import TransferRouteIndicator from '@/components/TransferRouteIndicator'
import RecentTransfersSkeleton from '@/components/RecentTransfersSkeleton'
import { buildTimeline, isTerminalStatus, overallState, type OverallState } from '@/lib/transferTimeline'
import { countryLabel } from '@/lib/countries'
import { getMyTransfers, type TransferStatus } from '@/lib/actions/transfer.actions'

const OVERALL_TO_JOURNEY_STATUS: Record<OverallState, JourneyCardStatus> = {
  delivered: 'done',
  in_progress: 'active',
  error: 'error',
  cancelled: 'cancelled',
}

/**
 * Correctif Skeleton — chargement CÔTÉ CLIENT (contrairement au reste du
 * tableau de bord, rendu serveur) : c'est le seul moyen de montrer un état de
 * chargement réellement visible pour l'utilisateur, un rendu serveur déjà
 * résolu n'en affiche jamais un au premier chargement.
 */
export default function RecentTransfersList() {
  const [transfers, setTransfers] = useState<TransferStatus[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const prefersReducedMotion = useReducedMotion()

  useEffect(() => {
    let cancelled = false
    getMyTransfers()
      .then((res) => {
        if (!cancelled) setTransfers(res.results)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Erreur de chargement')
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return (
      <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4">
        <AlertCircle size={16} className="text-red-500 mt-0.5 shrink-0" aria-hidden="true" />
        <p className="text-13 text-red-700">{error}</p>
      </div>
    )
  }

  if (transfers === null) {
    return <RecentTransfersSkeleton />
  }

  if (transfers.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 p-6 text-center">
        <p className="text-14 text-gray-500">
          Vous n&apos;avez pas encore effectué de transfert.
        </p>
        <Link
          href="/transfer"
          className="inline-flex items-center gap-1 mt-2 text-13 font-semibold text-blue-600 hover:underline max-md:min-h-11"
        >
          Envoyer votre premier transfert <ArrowRight size={14} />
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 md:gap-3">
      {transfers.map((t, i) => {
        const terminal = isTerminalStatus(t.status)
        return (
          // Correctif Framer Motion (1/3) — apparition en cascade légère
          // (~60ms entre chaque carte), pas un effet spectaculaire ; désactivée
          // si prefers-reduced-motion (useReducedMotion explicite).
          <motion.div
            key={t.transaction_id}
            initial={prefersReducedMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: prefersReducedMotion ? 0 : i * 0.06 }}
          >
            <JourneyCard
              beneficiaryName={t.beneficiary_name}
              beneficiaryCity={countryLabel(t.beneficiary_country)}
              amountEur={parseFloat(t.amount_eur)}
              status={OVERALL_TO_JOURNEY_STATUS[overallState(t.status)]}
              href={`/transfer/${t.transaction_id}`}
              routeIndicator={
                !terminal ? (
                  <TransferRouteIndicator
                    steps={buildTimeline({
                      status: t.status,
                      beneficiaryName: t.beneficiary_name,
                      operator: t.operator,
                      escrowTxHash: t.escrow_tx_hash,
                      payoutReference: t.payout_reference,
                      createdAt: t.created_at,
                      updatedAt: t.updated_at,
                      escrowedAt: t.escrowed_at,
                      batchTxHash: t.batch_tx_hash,
                      batchId: t.batch_id,
                    })}
                    mode="mini"
                  />
                ) : undefined
              }
            />
          </motion.div>
        )
      })}
    </div>
  )
}
