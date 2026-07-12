import { cn } from '@/lib/utils'
import { deriveRouteState, type RouteState } from '@/lib/transferRoute'
import type { TimelineStep } from '@/lib/transferTimeline'

export interface TransferRouteIndicatorProps {
  /** Réutilise la même source de vérité que TransferTimeline (KRYP-27) — pas
   * de seconde logique de dérivation de statut. */
  steps: TimelineStep[]
  mode?: 'mini' | 'full'
  originLabel?: string
  destinationLabel?: string
  className?: string
}

const STATE_COLOR: Record<RouteState, string> = {
  active: '#1570EF', // blue-600
  done: '#039855', // success-600
  error: '#DC2626', // red-600
  cancelled: '#98A2B3', // gray
}

/**
 * Composant signature (refonte frontend, partie 1/4) : route horizontale
 * SVG origine → destination, segment parcouru animé en pointillés défilants
 * tant que le transfert est actif. `mode="mini"` pour les listes (dashboard,
 * historique), `mode="full"` pour la page de suivi (KRYP-27).
 */
export default function TransferRouteIndicator({
  steps,
  mode = 'full',
  originLabel = 'Vous',
  destinationLabel = 'Bénéficiaire',
  className,
}: TransferRouteIndicatorProps) {
  const { progress, state } = deriveRouteState(steps)
  const color = STATE_COLOR[state]
  const isMini = mode === 'mini'
  const viewHeight = isMini ? 20 : 32
  const midY = viewHeight / 2
  const dotRadius = isMini ? 2.5 : 4
  const progressX = 4 + progress * 92

  return (
    <div
      className={cn('w-full', className)}
      data-testid="transfer-route-indicator"
      data-mode={mode}
    >
      <svg
        viewBox={`0 0 100 ${viewHeight}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height: isMini ? 16 : 28 }}
        role="img"
        aria-label={`Progression du transfert : ${Math.round(progress * 100)}%`}
      >
        <line
          x1="4"
          y1={midY}
          x2="96"
          y2={midY}
          stroke="#EAECF0"
          strokeWidth={isMini ? 2 : 3}
          strokeLinecap="round"
        />
        <line
          x1="4"
          y1={midY}
          x2={progressX}
          y2={midY}
          stroke={color}
          strokeWidth={isMini ? 2 : 3}
          strokeLinecap="round"
          strokeDasharray={state === 'active' ? '4 3' : undefined}
          className={state === 'active' ? 'animate-route-dash motion-reduce:animate-none' : undefined}
        />
        <circle cx="4" cy={midY} r={dotRadius} fill="#00214F" />
        {state === 'active' && (
          <circle
            cx={progressX}
            cy={midY}
            r={dotRadius + 1}
            fill={color}
            className="animate-timeline-pulse motion-reduce:animate-none"
          />
        )}
        <circle
          cx="96"
          cy={midY}
          r={dotRadius}
          fill={state === 'done' ? color : '#FFFFFF'}
          stroke={state === 'done' ? color : '#D0D5DD'}
          strokeWidth="1.5"
        />
      </svg>

      {!isMini && (
        <div className="flex items-center justify-between mt-1.5">
          <span className="text-12 font-medium text-gray-600">{originLabel}</span>
          <span className="text-12 font-medium text-gray-600">{destinationLabel}</span>
        </div>
      )}
    </div>
  )
}
