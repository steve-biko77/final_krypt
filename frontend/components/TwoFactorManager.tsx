'use client'

import { useTransition, useState } from 'react'
import Image from 'next/image'
import { Button } from '@/components/ui/button'
import { Loader2, ShieldCheck, ShieldOff, Copy, CheckCircle } from 'lucide-react'
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
      <div className="flex flex-col gap-6 p-6 rounded-xl border border-green-200 bg-green-50">
        <div className="flex items-center gap-3">
          <CheckCircle size={24} className="text-green-600" />
          <h2 className="text-18 font-semibold text-green-900">
            2FA activée avec succès
          </h2>
        </div>
        <div className="flex flex-col gap-3">
          <p className="text-14 font-semibold text-gray-800">
            Codes de récupération — notez-les maintenant, ils ne seront plus affichés.
          </p>
          <div className="grid grid-cols-2 gap-2">
            {step.codes.map((code) => (
              <code
                key={code}
                className="font-mono text-13 bg-white border border-green-200 rounded px-3 py-2 text-center"
              >
                {code}
              </code>
            ))}
          </div>
        </div>
        <Button
          onClick={() => setStep({ type: 'idle' })}
          className="form-btn"
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
          <ShieldOff size={24} className="text-gray-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-16 font-semibold text-gray-900">
              2FA désactivée
            </p>
            <p className="text-14 text-gray-500 mt-1">
              Activez la double authentification pour sécuriser votre compte.
              Vous aurez besoin d'une application comme Google Authenticator ou Authy.
            </p>
          </div>
        </div>

        {step.type === 'idle' && (
          <Button onClick={handleSetup} disabled={isPending} className="form-btn w-fit">
            {isPending ? (
              <>
                <Loader2 size={18} className="animate-spin mr-2" />
                Génération...
              </>
            ) : (
              'Activer la 2FA'
            )}
          </Button>
        )}

        {step.type === 'setup' && (
          <div className="flex flex-col gap-6 p-6 rounded-xl border border-blue-200 bg-blue-50">
            <h2 className="text-16 font-semibold text-blue-900">
              Étape 1 — Scannez le QR code
            </h2>
            <div className="flex justify-center">
              <Image
                src={`data:image/png;base64,${step.data.qr_image}`}
                alt="QR code 2FA"
                width={200}
                height={200}
                className="rounded-lg border border-blue-200"
              />
            </div>
            <div className="flex items-center gap-2">
              <p className="text-12 text-gray-600 font-mono flex-1 break-all">
                {step.data.secret}
              </p>
              <button
                type="button"
                onClick={() => copySecret(step.data.secret)}
                className="text-blue-600 hover:text-blue-800"
                title="Copier"
              >
                {copied ? <CheckCircle size={16} /> : <Copy size={16} />}
              </button>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-14 font-medium text-gray-700">
                Étape 2 — Entrez le code généré par votre application
              </label>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                placeholder="123456"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.trim())}
                className="input-class h-10 px-3 rounded-md border border-gray-300 text-center text-20 font-mono tracking-widest focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            {error && (
              <p className="text-14 text-red-500 font-medium">{error}</p>
            )}
            <div className="flex gap-3">
              <Button
                onClick={handleVerify}
                disabled={isPending || totpCode.length < 6}
                className="form-btn flex-1"
              >
                {isPending ? (
                  <>
                    <Loader2 size={18} className="animate-spin mr-2" />
                    Vérification...
                  </>
                ) : (
                  'Confirmer et activer'
                )}
              </Button>
              <Button
                variant="outline"
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
        <ShieldCheck size={24} className="text-green-600 shrink-0 mt-0.5" />
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
            className="input-class h-10 px-3 rounded-md border border-red-200 text-center text-20 font-mono tracking-widest focus:outline-none focus:ring-2 focus:ring-red-400"
          />
          {error && (
            <p className="text-14 text-red-600 font-medium">{error}</p>
          )}
          <div className="flex gap-3">
            <Button
              onClick={handleDisable}
              disabled={isPending || totpCode.length < 6}
              className="flex-1 bg-red-600 hover:bg-red-700 text-white"
            >
              {isPending ? (
                <>
                  <Loader2 size={18} className="animate-spin mr-2" />
                  Désactivation...
                </>
              ) : (
                'Désactiver'
              )}
            </Button>
            <Button
              variant="outline"
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
