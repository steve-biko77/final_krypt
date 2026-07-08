import { CheckCircle, Circle, XCircle, ExternalLink } from 'lucide-react'

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
    default:
      return 'Étape à venir'
  }
}

function StepIcon({ status }: { status: TimelineStep['status'] }) {
  const label = statusAriaLabel(status)
  const common = 'w-9 h-9 rounded-full flex items-center justify-center shrink-0'

  if (status === 'done') {
    return (
      <span className={`${common} bg-green-100 text-green-700`} role="img" aria-label={label}>
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
    default:
      return 'text-gray-400'
  }
}

export default function TransferTimeline({ steps }: { steps: TimelineStep[] }) {
  return (
    <ol className="flex flex-col">
      {steps.map((step, i) => {
        const isLast = i === steps.length - 1
        const time = formatTime(step.timestamp)
        // La ligne verticale reliant vers l'étape suivante est "atteinte"
        // (verte) si l'étape courante est done, sinon grise.
        const connectorColor = step.status === 'done' ? 'bg-green-200' : 'bg-gray-200'

        return (
          <li key={step.key} className="flex gap-4">
            {/* Colonne icône + connecteur vertical */}
            <div className="flex flex-col items-center">
              <StepIcon status={step.status} />
              {!isLast && <div className={`w-px flex-1 min-h-8 my-1 ${connectorColor}`} />}
            </div>

            {/* Contenu */}
            <div className={`flex-1 ${isLast ? '' : 'pb-6'}`}>
              <div className="flex items-baseline justify-between gap-3">
                <p className={`text-14 font-semibold ${labelColor(step.status)}`}>
                  {step.label}
                </p>
                {time && (
                  <span className="text-12 text-gray-400 font-mono shrink-0">{time}</span>
                )}
              </div>
              <p className="text-13 text-gray-600 mt-0.5">{step.description}</p>

              {step.txHash && (
                <a
                  href={`${POLYGONSCAN_TX}/${step.txHash}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 mt-2 text-12 font-medium text-blue-600 hover:text-blue-700 hover:underline rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1"
                >
                  <span className="font-mono">
                    {step.txHash.slice(0, 10)}…{step.txHash.slice(-8)}
                  </span>
                  <ExternalLink size={12} aria-hidden="true" />
                  <span className="sr-only">Voir la transaction sur Polygonscan</span>
                </a>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
