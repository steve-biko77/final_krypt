'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowDown, ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { convertEurToXafLocal, formatXaf, LOCAL_EUR_TO_XAF_RATE } from '@/lib/amountConverter'

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
 */
export default function AmountConverter({
  className,
  initialAmountEur = 100,
  ctaLabel = 'Envoyer maintenant',
  ctaHref,
  onSend,
}: AmountConverterProps) {
  const [amountInput, setAmountInput] = useState(String(initialAmountEur))
  const [popTick, setPopTick] = useState(0)

  const amountEur = Math.max(0, parseFloat(amountInput.replace(',', '.')) || 0)
  const conversion = convertEurToXafLocal(amountEur)

  // Rejoue la micro-animation "pop" (~180ms) à chaque recalcul du montant FCFA
  // en remontant le <span> (clé) — respecte prefers-reduced-motion via la
  // classe motion-reduce:animate-none (cf. tailwind.config.ts, amount-pop).
  useEffect(() => {
    setPopTick((t) => t + 1)
  }, [conversion.amountXaf])

  return (
    <div
      className={cn(
        'w-full rounded-2xl border border-gray-200 bg-white p-4 sm:p-6 shadow-form',
        className
      )}
      data-testid="amount-converter"
    >
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4">
        <label className="flex-1 min-w-0">
          <span className="block text-12 font-medium text-gray-500 mb-1">Vous envoyez</span>
          <div className="flex items-center gap-2 rounded-xl border border-gray-300 px-4 py-3 focus-within:ring-2 focus-within:ring-blue-500">
            <input
              type="text"
              inputMode="decimal"
              value={amountInput}
              onChange={(e) => setAmountInput(e.target.value)}
              aria-label="Montant en euros"
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
          <span className="block text-12 font-medium text-gray-500 mb-1">
            Le bénéficiaire reçoit
          </span>
          <div className="flex items-center gap-2 rounded-xl border border-gray-200 bg-gray-25 px-4 py-3">
            <span
              key={popTick}
              className="w-full font-mono text-20 tabular-nums font-semibold text-black-1 animate-amount-pop motion-reduce:animate-none"
              data-testid="amount-converter-result"
            >
              {formatXaf(conversion.amountXaf)}
            </span>
            <span className="text-14 font-mono text-gray-500 shrink-0">FCFA</span>
          </div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-4 pt-4 border-t border-gray-100">
        <p className="text-12 text-gray-500">
          Taux 1 EUR ={' '}
          <span className="font-mono tabular-nums">
            {LOCAL_EUR_TO_XAF_RATE.toString().replace('.', ',')}
          </span>{' '}
          FCFA · Frais 1,5 %
        </p>

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
