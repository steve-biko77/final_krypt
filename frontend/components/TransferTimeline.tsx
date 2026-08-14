import { CheckCircle, Circle, XCircle, ExternalLink } from 'lucide-react'

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { TimelineStep } from '@/lib/transferTimeline'

const POLYGONSCAN_TX = 'https://amoy.polygonscan.com/tx'

function formatTime(iso?: string): string | null {
  if (!iso) return null
  const d = new Date(iso)
  if (isNaN(d.getTime())) return null
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

/** Libellé accessible décrivant l'état en toutes lettres (pas seulement la couleur). */
function statusAriaLabel(status: TimelineStep['status']): string {
  switch (status) {
    case 'done':
      return 'Étape terminée'
    case 'active':
      return 'Étape en cours'
    case 'error':
      return 'Étape en erreur'
    case 'cancelled':
      return 'Étape annulée'
    default:
      return 'Étape à venir'
  }
}

// Palette alignée sur components/ui/badge.tsx (success/active/secondary/destructive)
// — mêmes tokens que JourneyCard, pour une cohérence de couleur réelle entre
// les deux, pas seulement une ressemblance visuelle approximative.
function StepIcon({ status }: { status: TimelineStep['status'] }) {
  const label = statusAriaLabel(status)
  const common = 'w-9 h-9 rounded-full flex items-center justify-center shrink-0'

  if (status === 'done') {
    return (
      <span className={`${common} bg-success-100 text-success-700`} role="img" aria-label={label}>
        <CheckCircle size={20} aria-hidden="true" />
      </span>
    )
  }
  if (status === 'error') {
    return (
      <span className={`${common} bg-red-100 text-red-700`} role="img" aria-label={label}>
        <XCircle size={20} aria-hidden="true" />
      </span>
    )
  }
  if (status === 'cancelled') {
    return (
      <span className={`${common} bg-gray-200 text-gray-500`} role="img" aria-label={label}>
        <XCircle size={20} aria-hidden="true" />
      </span>
    )
  }
  if (status === 'active') {
    return (
      <span
        className={`${common} bg-blue-600 text-white animate-timeline-pulse motion-reduce:animate-none`}
        role="img"
        aria-label={label}
      >
        <Circle size={12} fill="currentColor" aria-hidden="true" />
      </span>
    )
  }
  // pending
  return (
    <span className={`${common} bg-gray-100 text-gray-400`} role="img" aria-label={label}>
      <Circle size={12} aria-hidden="true" />
    </span>
  )
}

function labelColor(status: TimelineStep['status']): string {
  switch (status) {
    case 'done':
      return 'text-gray-900'
    case 'active':
      return 'text-blue-700'
    case 'error':
      return 'text-red-700'
    case 'cancelled':
      return 'text-gray-500'
    default:
      return 'text-gray-400'
  }
}

function cardBorderColor(status: TimelineStep['status']): string {
  switch (status) {
    case 'active':
      return 'border-blue-200'
    case 'error':
      return 'border-red-200'
    default:
      return 'border-gray-200'
  }
}

export default function TransferTimeline({ steps }: { steps: TimelineStep[] }) {
  return (
    <ol className="flex flex-col">
      {steps.map((step, i) => {
        const isLast = i === steps.length - 1
        const time = formatTime(step.timestamp)
        // La ligne verticale reliant vers l'étape suivante est "atteinte"
        // (success) si l'étape courante est done, sinon grise.
        const connectorColor = step.status === 'done' ? 'bg-success-100' : 'bg-gray-200'

        return (
          <li key={step.key} className="flex gap-4">
            {/* Colonne icône + connecteur vertical */}
            <div className="flex flex-col items-center">
              <StepIcon status={step.status} />
              {!isLast && <div className={`w-px flex-1 min-h-8 my-1 ${connectorColor}`} />}
            </div>

            {/* Carte de contenu par étape (point 3, partie 3/4) */}
            <div
              className={`flex-1 rounded-xl border bg-white p-4 ${cardBorderColor(step.status)} ${
                isLast ? '' : 'mb-4'
              }`}
            >
              <div className="flex items-baseline justify-between gap-3">
                <p className={`font-heading tracking-heading text-14 font-bold ${labelColor(step.status)}`}>
                  {step.label}
                </p>
                {time && (
                  <span className="text-12 font-mono tabular-nums text-gray-400 shrink-0">{time}</span>
                )}
              </div>
              <p className="text-13 text-gray-600 mt-1">{step.description}</p>

              {step.txHash && (
                <div className="mt-3 pt-3 border-t border-gray-100">
                  {/* Preuve on-chain volontairement mise en évidence (pas noyée
                      dans le reste, KRYP-27 ajout ultérieur) : pastille cliquable
                      distincte plutôt qu'un simple lien texte. */}
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <a
                        href={`${POLYGONSCAN_TX}/${step.txHash}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 rounded-lg bg-blue-25 px-2.5 py-1.5 text-12 font-medium text-blue-700 transition-colors hover:bg-blue-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 max-md:min-h-11 max-md:px-3"
                      >
                        {step.batchId != null ? (
                          // Preuve d'inclusion dans un lot Merkle AuditTrail (KRYP-27) —
                          // volontairement distincte d'un lien de transaction dédiée :
                          // ce hash prouve l'ancrage du lot, pas une transaction propre
                          // à ce transfert.
                          <>
                            <span>Inclus dans le lot Polygon #{step.batchId}</span>
                            <ExternalLink size={12} aria-hidden="true" />
                            <span className="sr-only">
                              Voir la preuve d&apos;inclusion du lot sur Polygonscan
                            </span>
                          </>
                        ) : (
                          <>
                            <span className="font-mono tabular-nums">
                              {step.txHash.slice(0, 10)}…{step.txHash.slice(-8)}
                            </span>
                            <ExternalLink size={12} aria-hidden="true" />
                            <span className="sr-only">Voir la transaction sur Polygonscan</span>
                          </>
                        )}
                      </a>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="max-w-56">
                        Polygonscan est un explorateur public de la blockchain Polygon : cette
                        preuve y est vérifiable par n&apos;importe qui, de façon permanente et
                        infalsifiable.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </div>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
