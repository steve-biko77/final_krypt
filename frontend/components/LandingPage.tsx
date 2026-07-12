import Image from 'next/image'
import Link from 'next/link'
import {
  UserPlus,
  Calculator,
  CreditCard,
  Smartphone,
  ShieldCheck,
  ExternalLink,
  Percent,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import AmountConverter from '@/components/AmountConverter'

const STEPS = [
  {
    icon: UserPlus,
    title: 'Inscription & vérification',
    description: "Créez votre compte et vérifiez votre identité (KYC) en quelques minutes.",
  },
  {
    icon: Calculator,
    title: 'Simulez votre transfert',
    description: 'Montant, frais et taux affichés clairement avant tout engagement.',
  },
  {
    icon: CreditCard,
    title: 'Paiement sécurisé',
    description: 'Votre carte bancaire est débitée et les fonds sont mis sous séquestre.',
  },
  {
    icon: Smartphone,
    title: 'Livraison Mobile Money',
    description: 'Le bénéficiaire reçoit les fonds sur MTN MoMo ou Orange Money.',
  },
] as const

/**
 * Page d'accueil publique (refonte frontend, partie 2/4) — accessible sans
 * connexion, rendue par (root)/page.tsx quand l'utilisateur n'est pas
 * authentifié. Le tableau de bord existant reste inchangé pour les
 * utilisateurs connectés.
 */
export default function LandingPage() {
  return (
    <div className="min-h-screen w-full bg-white">
      <header className="flex items-center justify-between px-5 sm:px-8 py-5 max-w-6xl mx-auto">
        <Link href="/" className="flex items-center gap-1.5">
          <Image src="/icons/logo.svg" width={30} height={30} alt="Krypt logo" />
          <span className="text-20 font-ibm-plex-serif font-bold text-black-1">Krypt</span>
        </Link>
        {/* h-11 (44px) explicite : taille tactile minimale mobile (point 5,
            partie 2/4) — size="sm" garde un padding horizontal compact. */}
        <nav className="flex items-center gap-2 sm:gap-3">
          <Button asChild variant="ghost" size="sm" className="h-11">
            <Link href="/sign-in">Se connecter</Link>
          </Button>
          <Button asChild variant="brand" size="sm" className="h-11">
            <Link href="/sign-up">Créer un compte</Link>
          </Button>
        </nav>
      </header>

      <main className="max-w-6xl mx-auto px-5 sm:px-8 flex flex-col gap-16 sm:gap-24 pb-24">
        {/* Hero */}
        <section className="flex flex-col gap-8 pt-8 sm:pt-12">
          <div className="max-w-2xl">
            <h1 className="font-heading tracking-heading text-30 sm:text-36 font-extrabold text-gray-900">
              Envoyez de l&apos;argent de France vers le Cameroun — en toute transparence.
            </h1>
            <p className="text-16 sm:text-18 text-gray-600 mt-4">
              Transferts rapides, frais annoncés à l&apos;avance, et chaque étape tracée sur la
              blockchain Polygon pour une preuve d&apos;exécution vérifiable.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 mt-6">
              <Button asChild variant="brand" size="lg" className="w-full sm:w-auto">
                <Link href="/sign-up">Créer un compte gratuitement</Link>
              </Button>
              <Button asChild variant="outline" size="lg" className="w-full sm:w-auto">
                <Link href="/sign-in">J&apos;ai déjà un compte</Link>
              </Button>
            </div>
          </div>

          <div className="max-w-xl">
            <p className="text-13 font-semibold text-gray-500 mb-2">
              Testez tout de suite — sans créer de compte
            </p>
            <AmountConverter
              initialAmountEur={100}
              ctaHref="/sign-up"
              ctaLabel="Créer un compte pour envoyer"
            />
          </div>
        </section>

        {/* Comment ça marche */}
        <section className="flex flex-col gap-8">
          <div>
            <h2 className="font-heading tracking-heading text-24 sm:text-30 font-bold text-gray-900">
              Comment ça marche
            </h2>
            <p className="text-14 text-gray-500 mt-1">Quatre étapes, du compte à la livraison.</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
            {STEPS.map((step, i) => {
              const Icon = step.icon
              return (
                <div
                  key={step.title}
                  className="flex flex-col gap-3 rounded-xl border border-gray-200 p-5"
                >
                  <div className="flex items-center gap-2">
                    <span className="flex size-8 items-center justify-center rounded-full bg-blue-25 font-mono text-13 font-semibold text-blue-700">
                      {i + 1}
                    </span>
                    <Icon size={20} className="text-blue-600" aria-hidden="true" />
                  </div>
                  <p className="text-14 font-semibold text-gray-900">{step.title}</p>
                  <p className="text-13 text-gray-500">{step.description}</p>
                </div>
              )
            })}
          </div>
        </section>

        {/* Indicateurs de confiance */}
        <section className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
          <div className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-gray-25 p-6">
            <div className="flex items-center gap-2">
              <ShieldCheck size={22} className="text-blue-600" aria-hidden="true" />
              <p className="text-16 font-semibold text-gray-900">Vérifiable sur la blockchain</p>
            </div>
            <p className="text-14 text-gray-600">
              Chaque étape critique de votre transfert (verrouillage des fonds, livraison) est
              journalisée sur le réseau Polygon via un contrat d&apos;audit public — une preuve
              d&apos;exécution que ni KRYPT ni personne d&apos;autre ne peut modifier a posteriori.
            </p>
            <a
              href="https://amoy.polygonscan.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-13 font-medium text-blue-600 hover:underline w-fit"
            >
              Explorer le réseau Polygon
              <ExternalLink size={13} aria-hidden="true" />
            </a>
          </div>

          <div className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-gray-25 p-6">
            <div className="flex items-center gap-2">
              <Percent size={22} className="text-success-600" aria-hidden="true" />
              <p className="text-16 font-semibold text-gray-900">Frais transparents</p>
            </div>
            <p className="text-14 text-gray-600">
              Le montant des frais est affiché avant tout engagement, sans surprise à l&apos;arrivée
              — contrairement aux frais souvent variables ou peu lisibles des opérateurs de
              transfert d&apos;argent traditionnels.
            </p>
          </div>
        </section>
      </main>
    </div>
  )
}
