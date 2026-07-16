'use client'

import { useEffect, useRef } from 'react'
import { ArrowDown, ArrowRight, Loader2 } from 'lucide-react'
import { animate, motion, useMotionValue, useReducedMotion, useTransform } from 'framer-motion'
import { cn } from '@/lib/utils'
import { formatXaf } from '@/lib/amountConverter'

export interface AmountConversionDisplayProps {
  className?: string
  amountEurValue: string
  onAmountEurChange: (value: string) => void
  /** Montant FCFA déjà calculé par l'appelant — `null` tant qu'aucun résultat
   * valide n'est disponible (montant vide/invalide, ou avant la première
   * réponse de simulation). Ce composant N'EFFECTUE AUCUN CALCUL. */
  amountXaf: number | null
  /** Simulation serveur en cours (debounce du tunnel de transfert) — affiche
   * un état de chargement au lieu du dernier montant XAF. */
  isLoading?: boolean
  fromLabel?: string
  toLabel?: string
  inputAriaLabel?: string
}

// Correctif Framer Motion (2/3) — remplace le "pop" d'échelle (partie 1/4)
// par un comptage numérique fluide vers la nouvelle valeur, plus lisible.
// Aucune animation au tout premier montage (rien dont "partir") : seuls les
// changements de valeur sur une instance déjà montée sont animés.
function AnimatedXafValue({ value }: { value: number }) {
  const prefersReducedMotion = useReducedMotion()
  const motionValue = useMotionValue(value)
  const display = useTransform(motionValue, (latest) => formatXaf(latest))
  const isFirstRender = useRef(true)

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      motionValue.set(value)
      return
    }
    if (prefersReducedMotion) {
      motionValue.set(value)
      return
    }
    const controls = animate(motionValue, value, { duration: 0.5, ease: 'easeOut' })
    return () => controls.stop()
  }, [value, motionValue, prefersReducedMotion])

  return (
    <motion.span
      className="w-full font-mono text-20 tabular-nums font-semibold text-black-1"
      data-testid="amount-conversion-result"
    >
      {display}
    </motion.span>
  )
}

/**
 * Langage visuel signature (refonte frontend, partie 1/4, extrait en
 * sous-composant partie 3/4) : deux champs côte à côte reliés par une flèche,
 * montant en police mono, comptage numérique fluide sur le résultat à chaque
 * changement (correctif Framer Motion). Purement présentationnel — réutilisé
 * avec deux sources de données différentes (calcul local dans
 * AmountConverter, simulation serveur réelle dans le tunnel de transfert)
 * pour une cohérence visuelle totale sans dupliquer le markup.
 */
export default function AmountConversionDisplay({
  className,
  amountEurValue,
  onAmountEurChange,
  amountXaf,
  isLoading = false,
  fromLabel = 'Vous envoyez',
  toLabel = 'Le bénéficiaire reçoit',
  inputAriaLabel = 'Montant en euros',
}: AmountConversionDisplayProps) {
  return (
    <div
      className={cn('flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4', className)}
      data-testid="amount-conversion-display"
    >
      <label className="flex-1 min-w-0">
        <span className="block text-12 font-medium text-gray-500 mb-1">{fromLabel}</span>
        <div className="flex items-center gap-2 rounded-xl border border-gray-300 px-4 py-3 focus-within:ring-2 focus-within:ring-blue-500">
          <input
            type="text"
            inputMode="decimal"
            value={amountEurValue}
            onChange={(e) => onAmountEurChange(e.target.value)}
            aria-label={inputAriaLabel}
            className="w-full min-w-0 bg-transparent font-mono text-20 tabular-nums text-gray-900 outline-none"
          />
          <span className="text-14 font-mono text-gray-500 shrink-0">EUR</span>
        </div>
      </label>

      <div
        className="flex sm:flex-col items-center justify-center text-blue-600 shrink-0"
        aria-hidden="true"
      >
        <ArrowRight size={20} className="sm:hidden" />
        <ArrowDown size={20} className="hidden sm:block" />
      </div>

      <div className="flex-1 min-w-0">
        <span className="block text-12 font-medium text-gray-500 mb-1">{toLabel}</span>
        <div className="flex items-center gap-2 rounded-xl border border-gray-200 bg-gray-25 px-4 py-3">
          {isLoading ? (
            <span
              className="flex w-full items-center gap-2 text-14 text-gray-400"
              data-testid="amount-conversion-loading"
            >
              <Loader2 size={16} className="animate-spin" aria-hidden="true" />
              Calcul en cours…
            </span>
          ) : amountXaf !== null ? (
            <AnimatedXafValue value={amountXaf} />
          ) : (
            <span
              className="w-full font-mono text-20 tabular-nums font-semibold text-black-1"
              data-testid="amount-conversion-result"
            >
              —
            </span>
          )}
          <span className="text-14 font-mono text-gray-500 shrink-0">FCFA</span>
        </div>
      </div>
    </div>
  )
}
