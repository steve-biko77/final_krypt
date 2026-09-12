import type { ReactNode } from 'react'
import AmountConverter from '@/components/AmountConverter'
import TransferRouteIndicator from '@/components/TransferRouteIndicator'
import JourneyCard from '@/components/JourneyCard'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import type { TimelineStep } from '@/lib/transferTimeline'

// ─────────────────────────────────────────────────────────────────────────
// PAGE DE DÉVELOPPEMENT — refonte frontend, partie 1/4.
// Vitrine isolée des fondations du design system (typographie, palette,
// composants signature, micro-interactions) pour validation visuelle rapide
// sans naviguer dans toute l'app. À RETIRER AVANT LA SOUTENANCE si elle n'a
// pas sa place en prod — jamais liée depuis la navigation principale.
// ─────────────────────────────────────────────────────────────────────────

function stepsFor(state: 'active' | 'done' | 'error' | 'cancelled'): TimelineStep[] {
  const base: TimelineStep[] = [
    { key: 'sent', label: 'Envoyé', description: '', status: 'done' },
    { key: 'compliance', label: 'Conformité', description: '', status: 'done' },
    { key: 'payment', label: 'Paiement', description: '', status: 'done' },
    { key: 'payout', label: 'Envoi', description: '', status: 'pending' },
    { key: 'delivered', label: 'Livré', description: '', status: 'pending' },
  ]

  if (state === 'active') {
    return base.map((s, i) => (i === 3 ? { ...s, status: 'active' } : s))
  }
  if (state === 'done') {
    return base.map((s) => ({ ...s, status: 'done' }))
  }
  if (state === 'error') {
    return base.map((s, i) => (i === 3 ? { ...s, status: 'error' } : s))
  }
  // cancelled
  return base.map((s, i) => (i === 1 ? { ...s, status: 'cancelled' } : s))
}

function Section({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section className="flex flex-col gap-4">
      <div>
        <h2 className="font-heading tracking-heading text-24 font-bold text-gray-900">{title}</h2>
        {description && <p className="text-14 text-gray-500 mt-1">{description}</p>}
      </div>
      {children}
    </section>
  )
}

export default function DesignSystemPage() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-12 p-4 sm:p-8">
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
        <p className="text-13 font-semibold text-amber-800">
          Page de développement — refonte frontend partie 1/4
        </p>
        <p className="text-12 text-amber-700 mt-1">
          Vitrine des fondations du design system, à retirer avant la soutenance. Jamais liée
          depuis la navigation principale.
        </p>
      </div>

      <div>
        <h1 className="font-heading tracking-heading text-36 font-extrabold text-black-1">
          Design system KRYPT
        </h1>
        <p className="text-16 text-gray-600 mt-2 max-w-2xl">
          Typographie, palette, composants signature et micro-interactions de la refonte
          frontend — fondations réutilisées par toutes les pages.
        </p>
      </div>

      <Section title="Typographie">
        <div className="flex flex-col gap-3">
          <p className="font-heading tracking-heading text-30 font-extrabold text-gray-900">
            Titre — Plus Jakarta Sans 800
          </p>
          <p className="font-heading tracking-heading text-24 font-bold text-gray-900">
            Titre — Plus Jakarta Sans 700
          </p>
          <p className="font-heading tracking-heading text-18 font-semibold text-gray-900">
            Titre — Plus Jakarta Sans 600
          </p>
          <p className="text-16 text-gray-600">
            Corps de texte — Inter (police système déjà en place, inchangée).
          </p>
          <p className="font-mono tabular-nums text-20 text-black-1">
            98 500,00 EUR → 64 611 FCFA — IBM Plex Mono, tabular-nums
          </p>
        </div>
      </Section>

      <Section title="Palette" description="Construite sur les couleurs KRYPT déjà en place.">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {[
            { label: 'Navy (accent fort)', className: 'bg-black-1' },
            { label: 'Bleu (action)', className: 'bg-blue-600' },
            { label: 'Succès', className: 'bg-success-600' },
            { label: 'Attention', className: 'bg-amber-500' },
            { label: 'Erreur', className: 'bg-red-600' },
            { label: 'Gris (neutre)', className: 'bg-gray-500' },
          ].map((swatch) => (
            <div key={swatch.label} className="flex items-center gap-3">
              <div className={`size-10 rounded-lg shrink-0 ${swatch.className}`} />
              <span className="text-13 text-gray-700">{swatch.label}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section
        title="AmountConverter"
        description="Calculateur d'envoi live — recalcul local à chaque frappe, taux et frais fixes."
      >
        <AmountConverter initialAmountEur={100} ctaLabel="Envoyer maintenant" />
      </Section>

      <Section
        title="TransferRouteIndicator"
        description="Route horizontale origine → destination, mode mini (listes) et full (suivi)."
      >
        <div className="flex flex-col gap-8">
          {(['active', 'done', 'error', 'cancelled'] as const).map((state) => (
            <div key={state} className="flex flex-col gap-2">
              <span className="text-12 font-medium uppercase tracking-wide text-gray-400">
                {state}
              </span>
              <TransferRouteIndicator
                steps={stepsFor(state)}
                mode="full"
                originLabel="Vous"
                destinationLabel="Jean, Yaoundé"
              />
              <div className="max-w-xs">
                <TransferRouteIndicator steps={stepsFor(state)} mode="mini" />
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="JourneyCard" description="Carte de transfert compacte pour les listes.">
        <div className="flex flex-col gap-3">
          <JourneyCard
            beneficiaryName="Jean Mbarga"
            beneficiaryCity="Yaoundé, Cameroun"
            amountEur={150}
            status="done"
            href="#"
          />
          <JourneyCard
            beneficiaryName="Aïcha Diallo"
            beneficiaryCity="Dakar, Sénégal"
            amountEur={80}
            status="active"
            href="#"
          />
          <JourneyCard
            beneficiaryName="Koffi Assamoah"
            beneficiaryCity="Abidjan, Côte d'Ivoire"
            amountEur={200}
            status="pending"
          />
          <JourneyCard
            beneficiaryName="Fatou Cissé"
            beneficiaryCity="Bamako, Mali"
            amountEur={45}
            status="error"
          />
        </div>
      </Section>

      <Section
        title="Boutons, badges, cartes"
        description="Micro-interaction commune : légère élévation au survol (~150ms), sauf le variant lien."
      >
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="brand">Brand</Button>
          <Button variant="default">Default</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="destructive">Destructive</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="link">Link (sans élévation)</Button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="success">Terminé</Badge>
          <Badge variant="active">En cours</Badge>
          <Badge variant="secondary">En attente</Badge>
          <Badge variant="warning">Attention</Badge>
          <Badge variant="destructive">Erreur</Badge>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Card interactive>
            <CardHeader>
              <CardTitle>Carte cliquable</CardTitle>
              <CardDescription>interactive — s&apos;élève au survol.</CardDescription>
            </CardHeader>
            <CardContent className="text-13 text-gray-500">
              Utiliser <code>interactive</code> uniquement si la carte déclenche une navigation
              ou une action.
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Carte informative</CardTitle>
              <CardDescription>par défaut — pas de micro-interaction.</CardDescription>
            </CardHeader>
            <CardContent className="text-13 text-gray-500">
              Contenu purement informatif, non cliquable.
            </CardContent>
          </Card>
        </div>
      </Section>
    </div>
  )
}
