'use client'

import Link from 'next/link'
import React, { useState } from 'react'
import Image from 'next/image'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import * as z from 'zod'
import { Button } from '@/components/ui/button'
import { Form } from '@/components/ui/form'
import CustomInput from './CustomInput'
import { AlertCircle, Loader2, ShieldCheck } from 'lucide-react'
import { completeTwoFactorSignIn, signIn, signUp } from '@/lib/actions/user.actions'
import { authFormSchema } from '@/lib/utils'
import { useRouter } from 'next/navigation'

// Tableau de bord admin — redirection automatique UNIQUEMENT juste après une
// connexion réussie (pas à chaque chargement de "/", cf. app/(root)/page.tsx)
// : ainsi le lien "Accueil" de la sidebar (route "/") continue de ramener un
// admin vers son dashboard personnel sans jamais rebondir vers /admin. La
// 2FA est requise en plus de is_staff — sinon /admin (IsStaffWith2FA côté
// backend) renverrait aussitôt l'admin vers "/", pour une boucle inutile.
function postLoginRedirectPath(user: { is_staff: boolean; is_2fa_enabled: boolean }): string {
  return user.is_staff && user.is_2fa_enabled ? '/admin' : '/'
}

// Refonte frontend (partie 2/4) — boîte d'erreur commune, calme et lisible
// (pas de rouge criard ni de ton anxiogène) : icône + texte, jamais juste du
// texte rouge brut.
function FormErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5">
      <AlertCircle size={16} className="text-red-500 shrink-0 mt-0.5" aria-hidden="true" />
      <p className="text-13 font-medium text-red-700">{message}</p>
    </div>
  )
}

const AuthForm = ({ type }: { type: 'sign-in' | 'sign-up' }) => {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 2FA intermediate state
  const [twoFaStep, setTwoFaStep] = useState(false)
  const [preAuthToken, setPreAuthToken] = useState<string | null>(null)
  const [totpCode, setTotpCode] = useState('')

  const formSchema = authFormSchema(type)

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: '',
      password: '',
      firstName: '',
      lastName: '',
      phone: '',
    },
  })

  const onSubmit = async (data: z.infer<typeof formSchema>) => {
    setIsLoading(true)
    setError(null)

    try {
      if (type === 'sign-up') {
        await signUp({
          email: data.email,
          password: data.password,
          firstName: data.firstName!,
          lastName: data.lastName!,
          phone: data.phone ?? '',
        })
        router.push('/')
      }

      if (type === 'sign-in') {
        const result = await signIn({ email: data.email, password: data.password })
        if (result.requires_2fa) {
          setPreAuthToken(result.pre_auth_token)
          setTwoFaStep(true)
        } else {
          router.push(postLoginRedirectPath(result.user))
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Une erreur est survenue')
    } finally {
      setIsLoading(false)
    }
  }

  const onTwoFaSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!preAuthToken) return
    setIsLoading(true)
    setError(null)

    try {
      const user = await completeTwoFactorSignIn({ pre_auth_token: preAuthToken, totp_code: totpCode })
      router.push(postLoginRedirectPath(user))
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Code invalide')
    } finally {
      setIsLoading(false)
    }
  }

  if (twoFaStep) {
    return (
      <section className="auth-form">
        <div className="w-full max-w-md rounded-2xl border border-gray-200 shadow-form p-6 sm:p-8">
          <header className="flex flex-col gap-5 md:gap-6">
            <Link href="/" className="cursor-pointer flex items-center gap-1">
              <Image src="/icons/logo.svg" width={34} height={34} alt="Krypt logo" />
              <span className="text-26 font-ibm-plex-serif font-bold text-black-1">Krypt</span>
            </Link>
            <div className="flex flex-col gap-1 md:gap-3">
              <div className="flex items-center gap-2">
                <ShieldCheck size={24} className="text-blue-600" aria-hidden="true" />
                <h1 className="font-heading tracking-heading text-24 lg:text-30 font-bold text-gray-900">
                  Vérification 2FA
                </h1>
              </div>
              <p className="text-16 font-normal text-gray-600">
                Entrez le code de votre application d&apos;authentification
              </p>
            </div>
          </header>

          <form onSubmit={onTwoFaSubmit} className="space-y-6 mt-6">
            <div className="flex flex-col gap-2">
              <label className="text-14 font-medium text-gray-700">
                Code à 6 chiffres
              </label>
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9A-Za-z\-]{1,20}"
                maxLength={20}
                placeholder="123456"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.trim())}
                required
                className="input-class h-11 px-3 rounded-lg border border-gray-300 text-center text-20 font-mono tabular-nums tracking-widest focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-12 text-gray-400">
                Vous pouvez aussi entrer un code de récupération.
              </p>
            </div>

            {error && <FormErrorBanner message={error} />}

            <div className="flex flex-col gap-3">
              <Button
                type="submit"
                variant="brand"
                size="lg"
                disabled={isLoading || totpCode.length < 6}
                className="w-full"
              >
                {isLoading ? (
                  <>
                    <Loader2 size={20} className="animate-spin" /> Vérification...
                  </>
                ) : (
                  'Confirmer'
                )}
              </Button>
              <button
                type="button"
                onClick={() => { setTwoFaStep(false); setPreAuthToken(null); setError(null) }}
                className="text-14 text-gray-500 underline underline-offset-2 py-2"
              >
                Retour à la connexion
              </button>
            </div>
          </form>
        </div>
      </section>
    )
  }

  return (
    <section className='auth-form'>
      <div className='w-full max-w-md rounded-2xl border border-gray-200 shadow-form p-6 sm:p-8 flex flex-col gap-6'>
        <header className='flex flex-col gap-5 md:gap-6'>
          <Link href='/' className='cursor-pointer flex items-center gap-1'>
            <Image src='/icons/logo.svg' width={34} height={34} alt='Krypt logo' />
            <span className='text-26 font-ibm-plex-serif font-bold text-black-1'>Krypt</span>
          </Link>
          <div className='flex flex-col gap-1 md:gap-3'>
            <h1 className='font-heading tracking-heading text-24 lg:text-30 font-bold text-gray-900'>
              {type === 'sign-in' ? 'Connexion' : 'Créer un compte'}
            </h1>
            <p className='text-16 font-normal text-gray-600'>
              {type === 'sign-in' ? 'Entrez vos identifiants' : 'Renseignez vos informations'}
            </p>
          </div>
        </header>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className='space-y-6'>
            {type === 'sign-up' && (
              <>
                <div className='flex gap-4'>
                  <CustomInput
                    control={form.control}
                    name='firstName'
                    label='Prénom'
                    placeholder='Votre prénom'
                  />
                  <CustomInput
                    control={form.control}
                    name='lastName'
                    label='Nom'
                    placeholder='Votre nom'
                  />
                </div>
                <CustomInput
                  control={form.control}
                  name='phone'
                  label='Téléphone'
                  placeholder='+33 6 12 34 56 78'
                />
              </>
            )}

            <CustomInput
              control={form.control}
              name='email'
              label='Email'
              placeholder='votre@email.com'
            />
            <CustomInput
              control={form.control}
              name='password'
              label='Mot de passe'
              placeholder='8 caractères minimum'
            />

            {error && <FormErrorBanner message={error} />}

            <div className='flex flex-col gap-4'>
              <Button type='submit' variant='brand' size='lg' disabled={isLoading} className='w-full'>
                {isLoading ? (
                  <>
                    <Loader2 size={20} className='animate-spin' /> Chargement...
                  </>
                ) : type === 'sign-in' ? 'Se connecter' : 'Créer un compte'}
              </Button>
            </div>
          </form>
        </Form>

        <footer className='flex justify-center gap-1'>
          <p className='text-14 font-normal text-gray-600'>
            {type === 'sign-in' ? "Pas encore de compte ?" : 'Déjà un compte ?'}
          </p>
          <Link
            href={type === 'sign-in' ? '/sign-up' : '/sign-in'}
            className='form-link'
          >
            {type === 'sign-in' ? 'Créer un compte' : 'Se connecter'}
          </Link>
        </footer>
      </div>
    </section>
  )
}

export default AuthForm
