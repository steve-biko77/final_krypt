'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { convertEurToXafLocal, LOCAL_EUR_TO_XAF_RATE } from '@/lib/amountConverter'
import AmountConversionDisplay from '@/components/AmountConversionDisplay'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

export interface AmountConverterProps {
  className?: string
  initialAmountEur?: number
  ctaLabel?: string
  /** Si fourni, le CTA devient un lien (ex. vers /transfer). */
  ctaHref?: string
  /** Si fourni (et ctaHref absent), le CTA appelle ce callback. */
  onSend?: (amountEur: number) => void
}

/**
 * Composant signature (refonte frontend, partie 1/4) : remplace la combinaison
 * "carte info taux + bouton CTA séparé" par un seul élément qui informe ET
 * déclenche l'action d'envoi. Calcul 100% local (taux + frais fixes) — aucun
 * appel réseau, contrairement à la simulation serveur du stepper de transfert.
 *
 * Refonte partie 3/4 — conteneur fin : ne fait QUE calculer (convertEurToXafLocal)
 * et nourrit le composant purement visuel AmountConversionDisplay, partagé à
 * l'identique avec le tunnel de transfert (simulation serveur réelle, voir
 * TransferStepper). Aucun markup dupliqué entre les deux.
 */
export default function AmountConverter({
  className,
  initialAmountEur = 100,
  ctaLabel = 'Envoyer maintenant',
  ctaHref,
  onSend,
}: AmountConverterProps) {
  const [amountInput, setAmountInput] = useState(String(initialAmountEur))

  const amountEur = Math.max(0, parseFloat(amountInput.replace(',', '.')) || 0)
  const conversion = convertEurToXafLocal(amountEur)

  return (
    <div
      className={cn(
        'w-full rounded-2xl border border-gray-200 bg-white p-4 sm:p-6 shadow-form',
        className
      )}
      data-testid="amount-converter"
    >
      <AmountConversionDisplay
        amountEurValue={amountInput}
        onAmountEurChange={setAmountInput}
        amountXaf={conversion.amountXaf}
      />

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-4 pt-4 border-t border-gray-100">
        <div className="flex items-center gap-1.5 text-12 text-gray-500">
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="outline" className="cursor-help">
                Taux fixe
              </Badge>
            </TooltipTrigger>
            <TooltipContent>
              <p className="max-w-56">
                Le FCFA (XAF) est arrimé à l&apos;euro à un taux fixe garanti — contrairement à
                une devise flottante, il ne varie pas d&apos;un jour à l&apos;autre.
              </p>
            </TooltipContent>
          </Tooltip>
          <p>
            1 EUR ={' '}
            <span className="font-mono tabular-nums">
              {LOCAL_EUR_TO_XAF_RATE.toString().replace('.', ',')}
            </span>{' '}
            FCFA · Frais 1,5 %
          </p>
        </div>

        {ctaHref ? (
          <Link
            href={ctaHref}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-13 font-semibold text-white transition-all duration-150 hover:-translate-y-0.5 hover:bg-blue-700"
          >
            {ctaLabel}
            <ArrowRight size={14} />
          </Link>
        ) : (
          <button
            type="button"
            onClick={() => onSend?.(amountEur)}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-13 font-semibold text-white transition-all duration-150 hover:-translate-y-0.5 hover:bg-blue-700"
          >
            {ctaLabel}
            <ArrowRight size={14} />
          </button>
        )}
      </div>
    </div>
  )
}
