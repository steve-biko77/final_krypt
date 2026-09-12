'use client'

import { useEffect, useRef, useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { AlertCircle, ArrowLeft, ArrowRight, Banknote, CheckCircle, Clock } from 'lucide-react'
import { loadStripe } from '@stripe/stripe-js'
import {
  CardElement,
  Elements,
  useElements,
  useStripe,
} from '@stripe/react-stripe-js'
import { toast } from 'sonner'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Button } from '@/components/ui/button'
import AmountConversionDisplay from '@/components/AmountConversionDisplay'
import BeneficiaryPicker from '@/components/BeneficiaryPicker'
import { detectMobileMoneyOperator } from '@/lib/detectMobileMoneyOperator'
import {
  saveBeneficiary,
  type SavedBeneficiary,
} from '@/lib/actions/beneficiaries.actions'
import {
  initiateTransfer,
  simulateTransfer,
  type TransferSimulation,
} from '@/lib/actions/transfer.actions'

// Chargé une seule fois au niveau module (clé publiable inlinée par Next.js).
const stripePromise = loadStripe(
  process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ?? '',
)

// Correctif IntegrationError Stripe — objet stable au niveau module plutôt
// qu'un littéral recréé à chaque rendu de PaymentForm (bonne pratique
// officielle react-stripe-js). Seul fontSize est nécessaire (règle anti-zoom
// iOS déjà appliquée ailleurs dans le tunnel, cf. .input-class) : lineHeight
// a été retiré, il n'apporte rien ici et simplifie la config au strict
// nécessaire — cf. chevauchement visuel mobile, corrigé côté conteneur
// (dimensions CSS) plutôt que côté Stripe.
const CARD_ELEMENT_OPTIONS = {
  style: { base: { fontSize: '16px' } },
}

type Operator = 'MTN_MOMO' | 'ORANGE_MONEY'
type Step = 'recipient' | 'amount' | 'payment'

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

export default function TransferStepper() {
  const [step, setStep] = useState<Step>('recipient')
  const prefersReducedMotion = useReducedMotion()
  // Correctif Framer Motion (3/3) — léger glissement horizontal + fondu entre
  // les 3 étapes, cohérent avec la métaphore du "parcours" (TransferRouteIndicator).
  const stepVariants = {
    initial: prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: 16 },
    animate: { opacity: 1, x: 0 },
    exit: prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: -16 },
  }
  const [recipient, setRecipient] = useState<RecipientData>({
    name: '',
    country: 'CM',
    mobileNumber: '',
    operator: 'MTN_MOMO',
  })
  // Détection auto de l'opérateur (point 4) — pré-sélectionne seulement,
  // jamais verrouillé : dès que l'utilisateur choisit manuellement, on arrête
  // de réécrire son choix même s'il continue à modifier le numéro.
  const [operatorAutoDetected, setOperatorAutoDetected] = useState(false)
  const [operatorManuallySet, setOperatorManuallySet] = useState(false)

  // Carnet de contacts — sélection dans BeneficiaryPicker (préremplissage) et
  // case "Enregistrer ce bénéficiaire" (opt-in, jamais cochée par défaut).
  const [selectedBeneficiaryId, setSelectedBeneficiaryId] = useState<string | null>(null)
  const [saveBeneficiaryChecked, setSaveBeneficiaryChecked] = useState(false)

  const handleSelectBeneficiary = (b: SavedBeneficiary) => {
    setRecipient({
      name: b.beneficiary_name,
      country: b.beneficiary_country,
      mobileNumber: b.momo_number,
      operator: b.operator,
    })
    setSelectedBeneficiaryId(b.id)
    // L'opérateur vient du bénéficiaire choisi, pas d'une détection : ne pas
    // le laisser être réécrit si l'utilisateur retouche le numéro ensuite.
    setOperatorManuallySet(true)
    setOperatorAutoDetected(false)
    setSaveBeneficiaryChecked(false)
  }

  const handleNewBeneficiary = () => {
    setRecipient({ name: '', country: 'CM', mobileNumber: '', operator: 'MTN_MOMO' })
    setSelectedBeneficiaryId(null)
    setOperatorManuallySet(false)
    setOperatorAutoDetected(false)
    setSaveBeneficiaryChecked(false)
  }

  const handleMobileNumberChange = (value: string) => {
    setRecipient((r) => ({ ...r, mobileNumber: value }))
    if (operatorManuallySet) return

    const detected = detectMobileMoneyOperator(value)
    if (detected) {
      setRecipient((r) => ({ ...r, operator: detected === 'MTN' ? 'MTN_MOMO' : 'ORANGE_MONEY' }))
      setOperatorAutoDetected(true)
    } else {
      setOperatorAutoDetected(false)
    }
  }
  const [amountStr, setAmountStr] = useState('')
  const [simulation, setSimulation] = useState<TransferSimulation | null>(null)
  const [simError, setSimError] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Étape 3 — paiement / conformité
  const [clientSecret, setClientSecret] = useState<string | null>(null)
  const [transactionId, setTransactionId] = useState<string | null>(null)
  const [pendingReview, setPendingReview] = useState(false)
  const [initiating, setInitiating] = useState(false)
  const [initError, setInitError] = useState<string | null>(null)

  const recipientValid =
    recipient.name.trim().length >= 2 &&
    recipient.mobileNumber.trim().length >= 8

  const handleConfirm = () => {
    const amount = parseFloat(amountStr)
    if (isNaN(amount) || amount <= 0) return
    setInitError(null)
    setInitiating(true)
    startTransition(async () => {
      try {
        const result = await initiateTransfer({
          beneficiary_name: recipient.name.trim(),
          beneficiary_country: recipient.country,
          momo_number: recipient.mobileNumber.trim(),
          operator: recipient.operator,
          amount_eur: amount,
        })
        if (result.status === 'PROCESSING' && result.client_secret) {
          setClientSecret(result.client_secret)
          setTransactionId(result.transaction_id)
          setStep('payment')
          toast.success('Transfert initié', {
            description: 'Il ne reste plus qu’à confirmer le paiement.',
          })
        } else if (result.status === 'AML_PENDING_REVIEW') {
          setTransactionId(result.transaction_id)
          setPendingReview(true)
          setStep('payment')
          toast.success('Transfert initié', {
            description: 'Il est en cours de vérification par nos équipes.',
          })
        }

        // Carnet de contacts — opt-in uniquement (case cochée), déclenché au
        // moment de l'initiation. Best-effort : un échec ici ne doit jamais
        // remettre en cause un transfert déjà initié avec succès.
        if (saveBeneficiaryChecked) {
          try {
            await saveBeneficiary({
              beneficiary_name: recipient.name.trim(),
              beneficiary_country: recipient.country,
              momo_number: recipient.mobileNumber.trim(),
              operator: recipient.operator,
            })
          } catch (e) {
            toast.error("Le bénéficiaire n'a pas pu être enregistré", {
              description: e instanceof Error ? e.message : undefined,
            })
          }
        }
      } catch (e) {
        setInitError(
          e instanceof Error ? e.message : 'Une erreur est survenue.',
        )
      } finally {
        setInitiating(false)
      }
    })
  }

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

  const STEP_LABELS: Record<Step, string> = {
    recipient: 'Destinataire',
    amount: 'Montant',
    payment: 'Paiement',
  }

  return (
    <div className="w-full max-w-xl">
      {/* Stepper header — libellés inline dès sm: ; en dessous, seul le
          libellé de l'étape courante s'affiche (repères + connecteurs
          resserrés) pour ne jamais déborder à 375px. */}
      <div className="flex items-center gap-2 sm:gap-3 mb-3 sm:mb-4">
        {(['recipient', 'amount', 'payment'] as Step[]).map((s, i) => {
          const order: Step[] = ['recipient', 'amount', 'payment']
          const currentIndex = order.indexOf(step)
          const done = i < currentIndex
          return (
            <div key={s} className="flex items-center gap-2 sm:gap-3">
              <div
                className={`flex items-center justify-center w-8 h-8 rounded-full font-mono text-14 font-bold tabular-nums transition-colors shrink-0 ${
                  step === s
                    ? 'bg-blue-600 text-white'
                    : done
                    ? 'bg-success-100 text-success-700'
                    : 'bg-gray-100 text-gray-400'
                }`}
              >
                {done ? (
                  // Petite touche de plaisir — le check "pop" à l'apparition
                  // au lieu de simplement remplacer le chiffre.
                  <motion.span
                    initial={prefersReducedMotion ? false : { scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 20 }}
                    className="flex items-center justify-center"
                  >
                    <CheckCircle size={16} />
                  </motion.span>
                ) : (
                  i + 1
                )}
              </div>
              <span
                className={`hidden sm:inline text-14 font-medium ${
                  step === s ? 'text-gray-900' : 'text-gray-400'
                }`}
              >
                {STEP_LABELS[s]}
              </span>
              {i < 2 && <div className="w-6 sm:w-12 h-px bg-gray-200 mx-1 shrink-0" />}
            </div>
          )
        })}
      </div>
      <p className="sm:hidden text-14 font-semibold text-gray-900 mb-4">
        {STEP_LABELS[step]}
      </p>

      <div className="rounded-2xl border border-gray-200 bg-white p-4 sm:p-6 shadow-form overflow-hidden">
      {/* mode par défaut ("sync", pas "wait") : la nouvelle étape apparaît
          immédiatement dans le DOM au lieu d'attendre la fin de la sortie de
          la précédente — évite tout délai perceptible au clic. */}
      <AnimatePresence>
      {/* ── STEP 1 : Destinataire ── */}
      {step === 'recipient' && (
        <motion.div
          key="recipient"
          variants={stepVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          transition={{ duration: 0.2 }}
          className="flex flex-col gap-5"
        >
          <BeneficiaryPicker
            selectedId={selectedBeneficiaryId}
            onSelect={handleSelectBeneficiary}
            onNew={handleNewBeneficiary}
          />

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
              className="w-full h-11 border border-gray-300 rounded-lg px-3 text-16 md:text-14 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              className="w-full h-11 border border-gray-300 rounded-lg px-3 text-16 md:text-14 text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              onChange={(e) => handleMobileNumberChange(e.target.value)}
              placeholder="+237 6XX XXX XXX"
              className="w-full h-11 border border-gray-300 rounded-lg px-3 text-16 md:text-14 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                  className={`flex-1 flex items-center gap-2 min-h-11 border rounded-lg px-4 py-3 cursor-pointer transition-colors ${
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
                    onChange={() => {
                      setRecipient((r) => ({ ...r, operator: op.value }))
                      setOperatorManuallySet(true)
                      setOperatorAutoDetected(false)
                    }}
                    className="accent-blue-600"
                  />
                  <span className="text-14 font-medium text-gray-800">
                    {op.label}
                  </span>
                </label>
              ))}
            </div>
            {/* Espace réservé sous mobile (min-h-6, ~hauteur du texte d'aide)
                que l'opérateur soit auto-détecté ou non : évite tout
                reflow/chevauchement avec le bouton "Suivant" dans l'état
                initial (avant saisie du numéro). md+ inchangé (0 réservé,
                comportement d'origine : rien si aucune détection). */}
            <div className="min-h-6 md:min-h-0">
              {operatorAutoDetected && (
                <p className="text-12 text-gray-400 mt-2">
                  Opérateur détecté automatiquement d&apos;après le numéro — modifiez si besoin.
                </p>
              )}
            </div>
          </div>

          {/* Opt-in explicite — jamais cochée par défaut, jamais de
              sauvegarde silencieuse. L'appel POST /beneficiaries n'a lieu
              qu'à l'initiation réelle du transfert (handleConfirm). */}
          <label className="flex items-center gap-2 min-h-11 cursor-pointer">
            <input
              type="checkbox"
              checked={saveBeneficiaryChecked}
              onChange={(e) => setSaveBeneficiaryChecked(e.target.checked)}
              className="size-4 accent-blue-600"
            />
            <span className="text-14 text-gray-700">
              Enregistrer ce bénéficiaire pour la prochaine fois
            </span>
          </label>

          {/* Pas de sticky ici (contrairement aux étapes Montant/Paiement) —
              cette étape est courte et tient sans scroll sur tous les
              écrans ; un bouton sticky basé sur un offset viewport pouvait se
              chevaucher avec le sélecteur d'opérateur juste au-dessus quand
              le contenu de l'étape est court (KRYP — correctif chevauchement
              mobile). */}
          <Button
            onClick={() => setStep('amount')}
            disabled={!recipientValid}
            variant="brand"
            size="lg"
            className="w-full mt-2"
          >
            Suivant <ArrowRight size={16} />
          </Button>
        </motion.div>
      )}

      {/* ── STEP 2 : Montant + Simulation ── */}
      {step === 'amount' && (
        <motion.div
          key="amount"
          variants={stepVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          transition={{ duration: 0.2 }}
          className="flex flex-col gap-5"
        >
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

          {/* Champ montant + résultat — composant visuel partagé avec
              AmountConverter (partie 1/4), alimenté ici par la VRAIE
              simulation serveur (source de vérité des règles métier/limites),
              jamais par un calcul local. */}
          <div>
            <AmountConversionDisplay
              amountEurValue={amountStr}
              onAmountEurChange={handleAmountChange}
              amountXaf={simulation ? parseFloat(simulation.amount_xaf) : null}
              isLoading={isPending}
              fromLabel="Montant à envoyer"
              toLabel="Le bénéficiaire reçoit"
              inputAriaLabel="Montant à envoyer en euros"
            />
            <p className="text-12 text-gray-400 mt-2">Min 5 EUR · Max 5 000 EUR</p>
          </div>

          {simError && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 border border-red-200">
              <AlertCircle size={16} className="text-red-500 mt-0.5 shrink-0" />
              <p className="text-13 text-red-700">{simError}</p>
            </div>
          )}

          {simulation && !isPending && (
            <div className="rounded-xl border border-gray-200 bg-gray-25 px-4 py-3 space-y-2">
              <div className="flex justify-between text-14">
                <span className="text-gray-500">
                  Frais KRYPT ({parseFloat(simulation.fees_percentage).toFixed(1)}%)
                </span>
                <span className="font-mono tabular-nums font-medium text-gray-900">
                  − {parseFloat(simulation.fees_eur).toFixed(2)} EUR
                </span>
              </div>
              <div className="flex justify-between text-14">
                <span className="text-gray-500">Montant net</span>
                <span className="font-mono tabular-nums font-medium text-gray-900">
                  {parseFloat(simulation.net_eur).toFixed(2)} EUR
                </span>
              </div>
              <div className="flex justify-between text-14">
                <span className="text-gray-500">Taux de change</span>
                <span className="font-mono tabular-nums font-medium text-gray-900">
                  1 EUR = {simulation.exchange_rate} XAF
                </span>
              </div>
            </div>
          )}

          {initError && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 border border-red-200">
              <AlertCircle size={16} className="text-red-500 mt-0.5 shrink-0" />
              <p className="text-13 text-red-700">{initError}</p>
            </div>
          )}

          <div
            className="flex gap-3 mt-2 max-md:sticky max-md:bottom-[calc(4.5rem+env(safe-area-inset-bottom))] max-md:z-10 max-md:-mx-4 max-md:border-t max-md:border-gray-100 max-md:bg-white max-md:px-4 max-md:py-3"
          >
            <Button
              onClick={() => setStep('recipient')}
              variant="outline"
              size="lg"
            >
              <ArrowLeft size={16} /> Retour
            </Button>
            <Button
              onClick={handleConfirm}
              disabled={!simulation || isPending || initiating}
              variant="brand"
              size="lg"
              className="flex-1"
            >
              {initiating ? 'Vérification en cours…' : 'Confirmer le transfert'}
            </Button>
          </div>
        </motion.div>
      )}

      {/* ── STEP 3 : Paiement / Conformité ── */}
      {step === 'payment' && (
        <motion.div
          key="payment"
          variants={stepVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          transition={{ duration: 0.2 }}
          className="flex flex-col gap-5"
        >
          {pendingReview ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 flex items-start gap-3">
              <Clock size={20} className="text-amber-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-14 font-semibold text-amber-800">
                  Votre transfert est en cours de vérification.
                </p>
                <p className="text-13 text-amber-700 mt-1">
                  Nos équipes examinent votre transfert. Vous serez notifié dès
                  qu&apos;il sera validé.
                </p>
                {transactionId && (
                  <p className="text-12 font-mono text-amber-600 mt-2">
                    Référence : {transactionId}
                  </p>
                )}
              </div>
            </div>
          ) : clientSecret ? (
            <Elements stripe={stripePromise} options={{ clientSecret }}>
              <PaymentForm clientSecret={clientSecret} transactionId={transactionId} />
            </Elements>
          ) : null}
        </motion.div>
      )}
      </AnimatePresence>
      </div>
    </div>
  )
}

// Redirection auto vers le suivi après confirmation du paiement — délai
// court (le webhook Stripe et le début du traitement backend sont déjà
// quasi immédiats) affiché de façon transparente, jamais silencieux.
const REDIRECT_DELAY_SECONDS = 3

function PaymentForm({
  clientSecret,
  transactionId,
}: {
  clientSecret: string
  transactionId: string | null
}) {
  const router = useRouter()
  const stripe = useStripe()
  const elements = useElements()
  const prefersReducedMotion = useReducedMotion()
  const [processing, setProcessing] = useState(false)
  const [payError, setPayError] = useState<string | null>(null)
  const [succeeded, setSucceeded] = useState(false)
  const [secondsLeft, setSecondsLeft] = useState(REDIRECT_DELAY_SECONDS)
  // Défensif (root cause IntegrationError) — le bouton ne doit jamais pouvoir
  // déclencher confirmCardPayment avant que l'Element ait émis 'ready'
  // (iframe montée) ET signalé complete:true (numéro/date/CVC valides). Sans
  // ces deux garde-fous, un clic rapide pouvait partir avant que Stripe
  // considère l'Element "mounted and ready".
  const [cardReady, setCardReady] = useState(false)
  const [cardComplete, setCardComplete] = useState(false)

  const goToTracking = () => {
    if (transactionId) router.push(`/transfer/${transactionId}`)
  }

  // Un seul setInterval (pas un setTimeout qui se reprogramme à chaque tick
  // depuis l'effet) : la redirection déclenche directement dans le callback
  // du timer, sans dépendre d'un nouveau cycle rendu/effet entre deux ticks.
  useEffect(() => {
    if (!succeeded || !transactionId) return
    const interval = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          clearInterval(interval)
          router.push(`/transfer/${transactionId}`)
          return 0
        }
        return s - 1
      })
    }, 1000)
    return () => clearInterval(interval)
  }, [succeeded, transactionId, router])

  const handlePay = async () => {
    if (!stripe || !elements || !cardReady || !cardComplete) return

    setProcessing(true)
    setPayError(null)
    // try/catch/finally englobe TOUT (récupération de l'Element ET l'appel
    // Stripe) — quelle que soit la nature de l'erreur (IntegrationError,
    // rejet Stripe, panne réseau), le bouton doit toujours se débloquer et
    // afficher un message clair, jamais rester bloqué sur "Paiement en cours…".
    try {
      const card = elements.getElement(CardElement)
      if (!card) {
        throw new Error("Le champ carte n'est pas prêt. Veuillez réessayer.")
      }

      const { error, paymentIntent } = await stripe.confirmCardPayment(
        clientSecret,
        { payment_method: { card } },
      )
      if (error) {
        const message = error.message ?? 'Le paiement a échoué.'
        setPayError(message)
        toast.error('Paiement refusé', { description: message })
        return
      }
      if (paymentIntent && paymentIntent.status === 'succeeded') {
        setSucceeded(true)
      }
    } catch (e) {
      const message =
        e instanceof Error ? e.message : 'Une erreur est survenue pendant le paiement. Réessayez.'
      setPayError(message)
      toast.error('Paiement impossible', { description: message })
    } finally {
      setProcessing(false)
    }
  }

  if (succeeded) {
    return (
      <div className="relative rounded-xl border border-green-200 bg-green-50 p-5 flex items-start gap-3 overflow-hidden">
        <CheckCircle size={20} className="text-green-600 mt-0.5 shrink-0" aria-hidden="true" />
        {/* Petite touche de plaisir — un billet qui "s'envole" au moment où
            le paiement est confirmé, une seule fois (pas de loop), retiré si
            prefers-reduced-motion. */}
        {!prefersReducedMotion && (
          <motion.span
            initial={{ opacity: 1, x: 0, y: 0, scale: 1, rotate: 0 }}
            animate={{ opacity: 0, x: 56, y: -36, scale: 0.6, rotate: 18 }}
            transition={{ duration: 0.9, ease: 'easeOut' }}
            className="pointer-events-none absolute right-4 top-4 text-green-500"
            aria-hidden="true"
          >
            <Banknote size={28} />
          </motion.span>
        )}
        <div>
          <p className="text-14 font-semibold text-green-800">
            Paiement confirmé.
          </p>
          <p className="text-13 text-green-700 mt-1">
            Votre transfert est en cours d&apos;acheminement vers le
            bénéficiaire.
          </p>
          {transactionId && (
            <div className="flex items-center gap-3 mt-3">
              <p className="text-12 text-green-600">
                Redirection vers le suivi dans {secondsLeft}s…
              </p>
              <button
                type="button"
                onClick={goToTracking}
                className="text-12 font-semibold text-blue-600 underline underline-offset-2 max-md:inline-flex max-md:min-h-11 max-md:items-center"
              >
                Voir le suivi maintenant
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-gray-200 p-4 sm:p-5">
      <div>
        <label className="block text-14 font-medium text-gray-700 mb-1">
          Carte bancaire
        </label>
        {/* Chevauchement visuel mobile — corrigé par les DIMENSIONS du
            conteneur (min-h généreux sous md) plutôt que par la config
            Stripe : à fontSize 16px, le champ carte combiné (numéro + date +
            CVC) a besoin de plus de hauteur pour rester lisible sans se
            chevaucher sur les petits écrans. Desktop (md+) inchangé. */}
        <div className="w-full min-h-11 max-md:min-h-16 flex items-center border border-gray-300 rounded-lg px-3 py-3 bg-white focus-within:ring-2 focus-within:ring-blue-500">
          <CardElement
            options={CARD_ELEMENT_OPTIONS}
            onReady={() => setCardReady(true)}
            onChange={(e) => setCardComplete(e.complete)}
            className="w-full"
          />
        </div>
      </div>

      {payError && (
        <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 border border-red-200">
          <AlertCircle size={16} className="text-red-500 mt-0.5 shrink-0" aria-hidden="true" />
          <p className="text-13 text-red-700">{payError}</p>
        </div>
      )}

      {/* Pas de sticky ici, même correctif que "Suivant" à l'étape
          Destinataire (résidu oublié lors de ce correctif-là) : l'étape
          Paiement (label + champ carte + erreur éventuelle) est courte et
          tient sans scroll, un bouton sticky s'y superposait au champ carte
          (KRYP — correctif chevauchement Payer/carte). Flux vertical normal
          (flex-col gap-4 du conteneur parent) suffit. */}
      <Button
        onClick={handlePay}
        disabled={!stripe || !cardReady || !cardComplete || processing}
        variant="brand"
        size="lg"
        className="w-full"
      >
        {processing ? 'Paiement en cours…' : 'Payer'}
      </Button>
    </div>
  )
}
