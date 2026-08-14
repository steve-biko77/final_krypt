import Link from 'next/link'
import { ShieldCheck } from 'lucide-react'
import KYCBanner from '@/components/KYCBanner'
import AmountConverter from '@/components/AmountConverter'
import RecentTransfersList from '@/components/RecentTransfersList'
import type { KYCDocumentStatus } from '@/lib/actions/kyc.actions'

export interface DashboardProps {
  firstName: string
  isKycVerified: boolean
  kycStatus: KYCDocumentStatus | null
}

/**
 * Tableau de bord authentifié (refonte frontend, partie 3/4). Ton chaleureux
 * (contrairement à la page 2FA, partie 2/4). Réutilise les composants
 * signature de la partie 1/4 (AmountConverter, JourneyCard,
 * TransferRouteIndicator) et la projection statut de KRYP-27
 * (buildTimeline/isTerminalStatus/overallState) — aucune nouvelle logique de
 * statut.
 */
export default function Dashboard({
  firstName,
  isKycVerified,
  kycStatus,
}: DashboardProps) {
  return (
    <div className="flex flex-col gap-8 p-4 sm:p-8 max-w-4xl">
      <div>
        <h1 className="font-heading tracking-heading text-24 sm:text-30 font-bold text-gray-900">
          Bienvenue, <span className="text-blue-600">{firstName}</span>
        </h1>
        <p className="text-16 md:text-14 text-gray-500 mt-1">
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
            className="text-13 font-medium text-blue-600 hover:underline whitespace-nowrap max-md:inline-flex max-md:min-h-11 max-md:items-center"
          >
            Historique complet →
          </Link>
        </div>

        <RecentTransfersList />
      </section>

      <div className="flex items-center gap-2">
        <ShieldCheck size={16} className="text-gray-400" aria-hidden="true" />
        <Link
          href="/security"
          className="text-13 font-medium text-gray-600 hover:text-blue-600 hover:underline max-md:inline-flex max-md:min-h-11 max-md:items-center"
        >
          Sécurité du compte (2FA) →
        </Link>
      </div>
    </div>
  )
}
