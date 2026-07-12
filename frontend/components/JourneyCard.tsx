import Link from 'next/link'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'

export type JourneyCardStatus = 'done' | 'active' | 'pending' | 'error'

const STATUS_BADGE: Record<JourneyCardStatus, { label: string; variant: 'success' | 'active' | 'secondary' | 'destructive' }> = {
  done: { label: 'Terminé', variant: 'success' },
  active: { label: 'En cours', variant: 'active' },
  pending: { label: 'En attente', variant: 'secondary' },
  error: { label: 'Erreur', variant: 'destructive' },
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  return parts.slice(0, 2).map((p) => p[0]!.toUpperCase()).join('')
}

export interface JourneyCardProps {
  beneficiaryName: string
  beneficiaryCity: string
  amountEur: number
  status: JourneyCardStatus
  /** Si fourni, la carte devient un lien cliquable (micro-interaction point 6). */
  href?: string
  className?: string
}

/**
 * Carte de transfert compacte (refonte frontend, partie 1/4) — utilisée dans
 * les listes (dashboard, historique). Sémantique de couleur de statut commune
 * à tout le projet (voir components/ui/badge.tsx).
 */
export default function JourneyCard({
  beneficiaryName,
  beneficiaryCity,
  amountEur,
  status,
  href,
  className,
}: JourneyCardProps) {
  const badge = STATUS_BADGE[status]
  const amountLabel = amountEur.toLocaleString('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

  const content = (
    <div
      className={cn(
        'flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-3 sm:p-4 transition-all duration-150',
        href && 'cursor-pointer hover:-translate-y-0.5 hover:shadow-chart',
        className
      )}
      data-testid="journey-card"
    >
      <div className="flex size-11 shrink-0 items-center justify-center rounded-full bg-blue-25 font-heading text-14 font-bold text-blue-700">
        {initials(beneficiaryName)}
      </div>

      <div className="min-w-0 flex-1">
        <p className="truncate text-14 font-semibold text-gray-900">{beneficiaryName}</p>
        <p className="truncate text-12 text-gray-500">{beneficiaryCity}</p>
      </div>

      <div className="flex shrink-0 flex-col items-end gap-1">
        <span className="font-mono text-14 tabular-nums font-semibold text-gray-900">
          {amountLabel} €
        </span>
        <Badge variant={badge.variant}>{badge.label}</Badge>
      </div>
    </div>
  )

  if (href) {
    return (
      <Link
        href={href}
        className="block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        {content}
      </Link>
    )
  }

  return content
}
