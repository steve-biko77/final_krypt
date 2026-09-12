'use client'

import { useTransition, useState } from 'react'
import Image from 'next/image'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { AlertTriangle, Loader2, ShieldCheck, ShieldOff, Copy, CheckCircle } from 'lucide-react'
import { setup2FA, verify2FA, disable2FA, type TwoFASetupData } from '@/lib/actions/twofa.actions'

type Step =
  | { type: 'idle' }
  | { type: 'setup'; data: TwoFASetupData }
  | { type: 'verifying' }
  | { type: 'codes'; codes: string[] }
  | { type: 'disabling' }

interface Props {
  is2faEnabled: boolean
}

const TwoFactorManager = ({ is2faEnabled }: Props) => {
  const [isPending, startTransition] = useTransition()
  const [enabled, setEnabled] = useState(is2faEnabled)
  const [step, setStep] = useState<Step>({ type: 'idle' })
  const [totpCode, setTotpCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const copySecret = (secret: string) => {
    navigator.clipboard.writeText(secret)
    setCopied(true)
    toast.success('Code copié dans le presse-papiers')
    setTimeout(() => setCopied(false), 2000)
  }

  const handleSetup = () => {
    setError(null)
    startTransition(async () => {
      try {
        const data = await setup2FA()
        setStep({ type: 'setup', data })
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Erreur lors de la génération du QR code')
      }
    })
  }

  const handleVerify = () => {
    setError(null)
    startTransition(async () => {
      try {
        const { recovery_codes } = await verify2FA(totpCode)
        setTotpCode('')
        setStep({ type: 'codes', codes: recovery_codes })
        setEnabled(true)
        toast.success('2FA activée')
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Code invalide')
      }
    })
  }

  const handleDisable = () => {
    setError(null)
    startTransition(async () => {
      try {
        await disable2FA(totpCode)
        setTotpCode('')
        setStep({ type: 'idle' })
        setEnabled(false)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Code invalide')
      }
    })
  }

  if (step.type === 'codes') {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3 rounded-xl border border-green-200 bg-green-50 p-4">
          <CheckCircle size={20} className="text-green-600 shrink-0" aria-hidden="true" />
          <p className="text-14 font-semibold text-green-900">2FA activée avec succès</p>
        </div>

        {/* Traitement volontairement sérieux (pas le ton chaleureux habituel de
            l'app) : contenu affiché une seule fois, à conserver précieusement. */}
        <div className="flex flex-col gap-4 rounded-xl border border-black-1 bg-black-1 p-5 sm:p-6">
          <div className="flex items-center gap-2">
            <AlertTriangle size={18} className="text-amber-400 shrink-0" aria-hidden="true" />
            <h2 className="font-heading tracking-heading text-16 font-bold text-white">
              Codes de récupération
            </h2>
          </div>
          <p className="text-13 text-gray-300">
            Notez-les et conservez-les dans un endroit sûr. Chaque code n&apos;est utilisable
            qu&apos;une seule fois, et cette liste ne sera{' '}
            <span className="font-semibold text-white">plus jamais affichée</span>.
          </p>
          {/* Codes au format "XXXX-XXXX-XXXX-XXXX" (19 caractères) : une seule
              colonne sous sm pour éviter tout débordement/retour à la ligne
              à 375px (voir contexts/identity/adapters/services/pyotp_service.py). */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {step.codes.map((code, i) => (
              <div
                key={code}
                className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2.5"
              >
                <span className="text-10 font-mono tabular-nums text-gray-400">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <code className="font-mono text-13 tabular-nums text-white">{code}</code>
              </div>
            ))}
          </div>
        </div>

        <Button
          onClick={() => setStep({ type: 'idle' })}
          variant="brand"
          size="lg"
          className="w-fit"
        >
          {"J'ai noté mes codes"}
        </Button>
      </div>
    )
  }

  if (!enabled) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex items-start gap-4 p-5 rounded-xl border border-gray-200 bg-gray-50">
          <ShieldOff size={24} className="text-gray-400 shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <p className="text-16 font-semibold text-gray-900">
              2FA désactivée
            </p>
            <p className="text-14 text-gray-500 mt-1">
              Activez la double authentification pour sécuriser votre compte.
              Vous aurez besoin d&apos;une application comme Google Authenticator ou Authy.
            </p>
          </div>
        </div>

        {step.type === 'idle' && (
          <Button onClick={handleSetup} variant="brand" size="lg" disabled={isPending} className="w-fit">
            {isPending ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Génération...
              </>
            ) : (
              'Activer la 2FA'
            )}
          </Button>
        )}

        {step.type === 'setup' && (
          <div className="flex flex-col gap-6 p-6 rounded-xl border border-black-1 bg-black-1">
            <h2 className="font-heading tracking-heading text-16 font-bold text-white">
              Étape 1 — Scannez le QR code
            </h2>
            <div className="flex justify-center rounded-lg bg-white p-4">
              <Image
                src={`data:image/png;base64,${step.data.qr_image}`}
                alt="QR code 2FA"
                width={200}
                height={200}
              />
            </div>
            <div className="flex items-center gap-2">
              <p className="text-12 text-gray-300 font-mono flex-1 break-all">
                {step.data.secret}
              </p>
              <button
                type="button"
                onClick={() => copySecret(step.data.secret)}
                className="flex items-center justify-center size-11 shrink-0 rounded-lg text-gray-300 hover:text-white hover:bg-white/10 transition-colors"
                title="Copier"
              >
                {copied ? <CheckCircle size={16} /> : <Copy size={16} />}
              </button>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-14 font-medium text-gray-200">
                Étape 2 — Entrez le code généré par votre application
              </label>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                placeholder="123456"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.trim())}
                className="h-11 px-3 rounded-lg border border-white/20 bg-white/5 text-center text-20 font-mono tabular-nums tracking-widest text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2.5">
                <AlertTriangle size={16} className="text-red-400 shrink-0 mt-0.5" aria-hidden="true" />
                <p className="text-13 font-medium text-red-300">{error}</p>
              </div>
            )}
            <div className="flex gap-3">
              <Button
                onClick={handleVerify}
                variant="brand"
                size="lg"
                disabled={isPending || totpCode.length < 6}
                className="flex-1"
              >
                {isPending ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Vérification...
                  </>
                ) : (
                  'Confirmer et activer'
                )}
              </Button>
              <Button
                variant="outline"
                size="lg"
                className="bg-transparent text-white border-white/20 hover:bg-white/10 hover:text-white"
                onClick={() => { setStep({ type: 'idle' }); setError(null); setTotpCode('') }}
              >
                Annuler
              </Button>
            </div>
          </div>
        )}
      </div>
    )
  }

  // 2FA is enabled
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start gap-4 p-5 rounded-xl border border-green-200 bg-green-50">
        <ShieldCheck size={24} className="text-green-600 shrink-0 mt-0.5" aria-hidden="true" />
        <div>
          <p className="text-16 font-semibold text-gray-900">2FA activée</p>
          <p className="text-14 text-gray-500 mt-1">
            Votre compte est protégé par une double authentification.
          </p>
        </div>
      </div>

      {step.type === 'idle' && (
        <Button
          variant="outline"
          size="lg"
          onClick={() => { setStep({ type: 'disabling' }); setError(null) }}
          className="w-fit text-red-600 border-red-200 hover:bg-red-50"
        >
          Désactiver la 2FA
        </Button>
      )}

      {step.type === 'disabling' && (
        <div className="flex flex-col gap-4 p-6 rounded-xl border border-red-200 bg-red-50">
          <p className="text-14 font-medium text-red-900">
            Entrez votre code TOTP actuel (ou un code de récupération) pour confirmer la désactivation.
          </p>
          <input
            type="text"
            inputMode="numeric"
            maxLength={20}
            placeholder="123456"
            value={totpCode}
            onChange={(e) => setTotpCode(e.target.value.trim())}
            className="input-class h-11 px-3 rounded-lg border border-red-200 text-center text-20 font-mono tabular-nums tracking-widest focus:outline-none focus:ring-2 focus:ring-red-400"
          />
          {error && (
            <p className="text-14 text-red-600 font-medium">{error}</p>
          )}
          <div className="flex gap-3">
            <Button
              onClick={handleDisable}
              size="lg"
              disabled={isPending || totpCode.length < 6}
              className="flex-1 bg-red-600 hover:bg-red-700 text-white"
            >
              {isPending ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Désactivation...
                </>
              ) : (
                'Désactiver'
              )}
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => { setStep({ type: 'idle' }); setError(null); setTotpCode('') }}
            >
              Annuler
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

export default TwoFactorManager
