'use client'

import { useEffect, useState } from 'react'
import { ArrowDown, ArrowRight, Loader2 } from 'lucide-react'
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

/**
 * Langage visuel signature (refonte frontend, partie 1/4, extrait en
 * sous-composant partie 3/4) : deux champs côte à côte reliés par une flèche,
 * montant en police mono, micro-animation sur le résultat à chaque
 * changement. Purement présentationnel — réutilisé avec deux sources de
 * données différentes (calcul local dans AmountConverter, simulation serveur
 * réelle dans le tunnel de transfert) pour une cohérence visuelle totale sans
 * dupliquer le markup.
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
  const [popTick, setPopTick] = useState(0)

  // Rejoue la micro-animation "pop" (~180ms) à chaque nouveau résultat — que
  // ce résultat vienne d'un calcul local instantané ou d'une réponse API
  // débouncée n'a aucune importance ici.
  useEffect(() => {
    if (amountXaf !== null) setPopTick((t) => t + 1)
  }, [amountXaf])

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
          ) : (
            <span
              key={popTick}
              className="w-full font-mono text-20 tabular-nums font-semibold text-black-1 animate-amount-pop motion-reduce:animate-none"
              data-testid="amount-conversion-result"
            >
              {amountXaf !== null ? formatXaf(amountXaf) : '—'}
            </span>
          )}
          <span className="text-14 font-mono text-gray-500 shrink-0">FCFA</span>
        </div>
      </div>
    </div>
  )
}
