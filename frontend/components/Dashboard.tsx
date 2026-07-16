import Link from 'next/link'
import { ArrowRight, ShieldCheck } from 'lucide-react'
import KYCBanner from '@/components/KYCBanner'
import AmountConverter from '@/components/AmountConverter'
import JourneyCard, { type JourneyCardStatus } from '@/components/JourneyCard'
import TransferRouteIndicator from '@/components/TransferRouteIndicator'
import { buildTimeline, isTerminalStatus, overallState, type OverallState } from '@/lib/transferTimeline'
import { countryLabel } from '@/lib/countries'
import type { KYCDocumentStatus } from '@/lib/actions/kyc.actions'
import type { TransferStatus } from '@/lib/actions/transfer.actions'

export interface DashboardProps {
  firstName: string
  isKycVerified: boolean
  kycStatus: KYCDocumentStatus | null
  transfers: TransferStatus[]
}

const OVERALL_TO_JOURNEY_STATUS: Record<OverallState, JourneyCardStatus> = {
  delivered: 'done',
  in_progress: 'active',
  error: 'error',
  cancelled: 'cancelled',
}

/**
 * Tableau de bord authentifié (refonte frontend, partie 3/4). Ton chaleureux
 * (contrairement à la page 2FA, partie 2/4). Réutilise les composants
 * signature de la partie 1/4 (AmountConverter, JourneyCard,
 * TransferRouteIndicator) et la projection statut de KRYP-27
 * (buildTimeline/isTerminalStatus/overallState) — aucune nouvelle logique de
 * statut.
 */
export default function Dashboard({ firstName, isKycVerified, kycStatus, transfers }: DashboardProps) {
  return (
    <div className="flex flex-col gap-8 p-4 sm:p-8 max-w-4xl">
      <div>
        <h1 className="font-heading tracking-heading text-24 sm:text-30 font-bold text-gray-900">
          Bienvenue, <span className="text-blue-600">{firstName}</span>
        </h1>
        <p className="text-14 text-gray-500 mt-1">
          Gérez vos transferts France → Cameroun via Mobile Money
        </p>
      </div>

      {!isKycVerified && <KYCBanner kycStatus={kycStatus} />}

      <AmountConverter ctaHref="/transfer" ctaLabel="Envoyer un transfert" />

      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="font-heading tracking-heading text-18 font-bold text-gray-900">
            Transferts récents
          </h2>
          <Link
            href="/transaction-history"
            className="text-13 font-medium text-blue-600 hover:underline whitespace-nowrap"
          >
            Historique complet →
          </Link>
        </div>

        {transfers.length === 0 ? (
          <div className="rounded-xl border border-gray-200 p-6 text-center">
            <p className="text-14 text-gray-500">
              Vous n&apos;avez pas encore effectué de transfert.
            </p>
            <Link
              href="/transfer"
              className="inline-flex items-center gap-1 mt-2 text-13 font-semibold text-blue-600 hover:underline"
            >
              Envoyer votre premier transfert <ArrowRight size={14} />
            </Link>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {transfers.map((t) => {
              const terminal = isTerminalStatus(t.status)
              return (
                <JourneyCard
                  key={t.transaction_id}
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
              )
            })}
          </div>
        )}
      </section>

      <div className="flex items-center gap-2">
        <ShieldCheck size={16} className="text-gray-400" aria-hidden="true" />
        <Link href="/security" className="text-13 font-medium text-gray-600 hover:text-blue-600 hover:underline">
          Sécurité du compte (2FA) →
        </Link>
      </div>
    </div>
  )
}
