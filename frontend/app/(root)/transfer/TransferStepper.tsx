'use client'

import { useRef, useState, useTransition } from 'react'
import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle } from 'lucide-react'
import { simulateTransfer, type TransferSimulation } from '@/lib/actions/transfer.actions'

type Operator = 'MTN_MOMO' | 'ORANGE_MONEY'
type Step = 'recipient' | 'amount'

interface RecipientData {
  name: string
  country: string
  mobileNumber: string
  operator: Operator
}

const COUNTRIES = [
  { code: 'CM', label: 'Cameroun (+237)' },
  { code: 'FR', label: 'France (+33)' },
  { code: 'SN', label: 'Sénégal (+221)' },
  { code: 'CI', label: "Côte d'Ivoire (+225)" },
]

function formatXAF(xaf: string): string {
  return Math.round(parseFloat(xaf)).toLocaleString('fr-FR')
}

export default function TransferStepper() {
  const [step, setStep] = useState<Step>('recipient')
  const [recipient, setRecipient] = useState<RecipientData>({
    name: '',
    country: 'CM',
    mobileNumber: '',
    operator: 'MTN_MOMO',
  })
  const [amountStr, setAmountStr] = useState('')
  const [simulation, setSimulation] = useState<TransferSimulation | null>(null)
  const [simError, setSimError] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const recipientValid =
    recipient.name.trim().length >= 2 &&
    recipient.mobileNumber.trim().length >= 8

  const handleAmountChange = (value: string) => {
    setAmountStr(value)
    setSimulation(null)
    setSimError(null)
    if (debounceRef.current) clearTimeout(debounceRef.current)

    const amount = parseFloat(value)
    if (!value || isNaN(amount) || amount <= 0) return

    debounceRef.current = setTimeout(() => {
      startTransition(async () => {
        try {
          const sim = await simulateTransfer(amount)
          setSimulation(sim)
          setSimError(null)
        } catch (e) {
          setSimError(e instanceof Error ? e.message : 'Erreur de simulation')
          setSimulation(null)
        }
      })
    }, 300)
  }

  return (
    <div className="w-full max-w-xl">
      {/* Stepper header */}
      <div className="flex items-center gap-3 mb-8">
        {(['recipient', 'amount'] as Step[]).map((s, i) => (
          <div key={s} className="flex items-center gap-3">
            <div
              className={`flex items-center justify-center w-8 h-8 rounded-full text-14 font-bold transition-colors ${
                step === s
                  ? 'bg-blue-600 text-white'
                  : i === 0 && step === 'amount'
                  ? 'bg-green-100 text-green-700'
                  : 'bg-gray-100 text-gray-400'
              }`}
            >
              {i === 0 && step === 'amount' ? (
                <CheckCircle size={16} />
              ) : (
                i + 1
              )}
            </div>
            <span
              className={`text-14 font-medium ${
                step === s ? 'text-gray-900' : 'text-gray-400'
              }`}
            >
              {s === 'recipient' ? 'Destinataire' : 'Montant'}
            </span>
            {i === 0 && (
              <div className="w-12 h-px bg-gray-200 mx-1" />
            )}
          </div>
        ))}
      </div>

      {/* ── STEP 1 : Destinataire ── */}
      {step === 'recipient' && (
        <div className="flex flex-col gap-5">
          <div>
            <label className="block text-14 font-medium text-gray-700 mb-1">
              Nom complet du bénéficiaire
            </label>
            <input
              type="text"
              value={recipient.name}
              onChange={(e) =>
                setRecipient((r) => ({ ...r, name: e.target.value }))
              }
              placeholder="Jean-Pierre Mbarga"
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-14 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-14 font-medium text-gray-700 mb-1">
              Pays
            </label>
            <select
              value={recipient.country}
              onChange={(e) =>
                setRecipient((r) => ({ ...r, country: e.target.value }))
              }
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-14 text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-14 font-medium text-gray-700 mb-1">
              Numéro Mobile Money
            </label>
            <input
              type="tel"
              value={recipient.mobileNumber}
              onChange={(e) =>
                setRecipient((r) => ({ ...r, mobileNumber: e.target.value }))
              }
              placeholder="+237 6XX XXX XXX"
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-14 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <p className="block text-14 font-medium text-gray-700 mb-2">
              Opérateur Mobile Money
            </p>
            <div className="flex gap-3">
              {(
                [
                  { value: 'MTN_MOMO', label: 'MTN MoMo' },
                  { value: 'ORANGE_MONEY', label: 'Orange Money' },
                ] as { value: Operator; label: string }[]
              ).map((op) => (
                <label
                  key={op.value}
                  className={`flex-1 flex items-center gap-2 border rounded-lg px-4 py-3 cursor-pointer transition-colors ${
                    recipient.operator === op.value
                      ? 'border-blue-600 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="operator"
                    value={op.value}
                    checked={recipient.operator === op.value}
                    onChange={() =>
                      setRecipient((r) => ({ ...r, operator: op.value }))
                    }
                    className="accent-blue-600"
                  />
                  <span className="text-14 font-medium text-gray-800">
                    {op.label}
                  </span>
                </label>
              ))}
            </div>
          </div>

          <button
            onClick={() => setStep('amount')}
            disabled={!recipientValid}
            className="flex items-center justify-center gap-2 w-full py-3 rounded-lg bg-blue-600 text-white text-14 font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition mt-2"
          >
            Suivant <ArrowRight size={16} />
          </button>
        </div>
      )}

      {/* ── STEP 2 : Montant + Simulation ── */}
      {step === 'amount' && (
        <div className="flex flex-col gap-5">
          {/* Récapitulatif destinataire */}
          <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
            <p className="text-12 text-gray-500 mb-1">Destinataire</p>
            <p className="text-14 font-semibold text-gray-900">{recipient.name}</p>
            <p className="text-13 text-gray-600">
              {recipient.mobileNumber} ·{' '}
              {recipient.operator === 'MTN_MOMO' ? 'MTN MoMo' : 'Orange Money'} ·{' '}
              {COUNTRIES.find((c) => c.code === recipient.country)?.label ?? recipient.country}
            </p>
          </div>

          {/* Champ montant */}
          <div>
            <label className="block text-14 font-medium text-gray-700 mb-1">
              Montant à envoyer (EUR)
            </label>
            <div className="relative">
              <input
                type="number"
                min="5"
                max="5000"
                step="1"
                value={amountStr}
                onChange={(e) => handleAmountChange(e.target.value)}
                placeholder="Ex : 100"
                className="w-full border border-gray-300 rounded-lg px-3 py-2.5 pr-14 text-14 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-14 font-medium text-gray-500">
                EUR
              </span>
            </div>
            <p className="text-12 text-gray-400 mt-1">Min 5 EUR · Max 5 000 EUR</p>
          </div>

          {/* Simulation en temps réel */}
          {isPending && (
            <div className="flex items-center gap-2 text-14 text-gray-400 py-2">
              <span className="animate-spin inline-block w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full" />
              Calcul en cours…
            </div>
          )}

          {simError && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 border border-red-200">
              <AlertCircle size={16} className="text-red-500 mt-0.5 shrink-0" />
              <p className="text-13 text-red-700">{simError}</p>
            </div>
          )}

          {simulation && !isPending && (
            <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
              <div className="px-4 py-3 space-y-2">
                <div className="flex justify-between text-14">
                  <span className="text-gray-500">Montant envoyé</span>
                  <span className="font-medium text-gray-900">
                    {parseFloat(simulation.amount_eur).toFixed(2)} EUR
                  </span>
                </div>
                <div className="flex justify-between text-14">
                  <span className="text-gray-500">
                    Frais KRYPT ({parseFloat(simulation.fees_percentage).toFixed(1)}%)
                  </span>
                  <span className="font-medium text-gray-900">
                    − {parseFloat(simulation.fees_eur).toFixed(2)} EUR
                  </span>
                </div>
                <div className="flex justify-between text-14">
                  <span className="text-gray-500">Montant net</span>
                  <span className="font-medium text-gray-900">
                    {parseFloat(simulation.net_eur).toFixed(2)} EUR
                  </span>
                </div>
                <div className="flex justify-between text-14">
                  <span className="text-gray-500">Taux de change</span>
                  <span className="font-medium text-gray-900">
                    1 EUR = {simulation.exchange_rate} XAF
                  </span>
                </div>
              </div>
              <div className="border-t border-gray-200 px-4 py-4 bg-green-50">
                <div className="flex justify-between items-center">
                  <span className="text-14 font-semibold text-gray-700">
                    Montant reçu
                  </span>
                  <span className="text-22 font-bold text-green-700">
                    {formatXAF(simulation.amount_xaf)} FCFA
                  </span>
                </div>
              </div>
            </div>
          )}

          <div className="flex gap-3 mt-2">
            <button
              onClick={() => setStep('recipient')}
              className="flex items-center justify-center gap-2 px-5 py-3 rounded-lg border border-gray-300 text-gray-700 text-14 font-semibold hover:bg-gray-50 transition"
            >
              <ArrowLeft size={16} /> Retour
            </button>
            <button
              disabled
              title="Disponible dans KRYP-21"
              className="flex-1 py-3 rounded-lg bg-blue-600 text-white text-14 font-semibold opacity-40 cursor-not-allowed"
            >
              Confirmer le transfert
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
