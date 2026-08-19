import { useEffect } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TransferStepper from './TransferStepper'
import { initiateTransfer, simulateTransfer } from '@/lib/actions/transfer.actions'
import { getSavedBeneficiaries, saveBeneficiary } from '@/lib/actions/beneficiaries.actions'
import type { SavedBeneficiary } from '@/lib/actions/beneficiaries.actions'

const routerPush = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: routerPush }),
}))

// Stripe.js n'a rien à faire dans les tests de l'étape simulation (on ne
// dépasse pas l'étape 2) — stubs par défaut. Les tests de redirection
// post-paiement (étape 3) surchargent confirmCardPayment/getElement via
// vi.mocked pour simuler un paiement réussi sans dépendre de Stripe réel.
vi.mock('@stripe/stripe-js', () => ({ loadStripe: () => Promise.resolve(null) }))
const confirmCardPayment = vi.fn()
vi.mock('@stripe/react-stripe-js', () => ({
  Elements: ({ children }: { children: React.ReactNode }) => children,
  // Simule une carte montée (onReady) et complète (onChange complete:true)
  // dès le rendu — cf. le garde-fou cardReady/cardComplete de PaymentForm,
  // qui bloquerait sinon le bouton "Payer" dans tous les tests existants.
  CardElement: ({
    onReady,
    onChange,
  }: {
    onReady?: () => void
    onChange?: (e: { complete: boolean }) => void
  }) => {
    useEffect(() => {
      onReady?.()
      onChange?.({ complete: true })
    }, [onReady, onChange])
    return null
  },
  useElements: () => ({ getElement: () => ({}) }),
  useStripe: () => ({ confirmCardPayment }),
}))

vi.mock('@/lib/actions/transfer.actions', () => ({
  simulateTransfer: vi.fn(),
  initiateTransfer: vi.fn(),
}))

// Carnet de contacts — BeneficiaryPicker (monté sur l'étape Destinataire)
// appelle getSavedBeneficiaries au montage ; liste vide par défaut pour ne
// rien changer aux tests existants (le picker ne rend alors rien).
vi.mock('@/lib/actions/beneficiaries.actions', () => ({
  getSavedBeneficiaries: vi.fn().mockResolvedValue([]),
  saveBeneficiary: vi.fn(),
  deleteBeneficiary: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.mocked(getSavedBeneficiaries).mockResolvedValue([])
})

async function goToAmountStep(user: ReturnType<typeof userEvent.setup>) {
  render(<TransferStepper />)

  await user.type(screen.getByPlaceholderText('Jean-Pierre Mbarga'), 'Jean Mbarga')
  await user.type(screen.getByPlaceholderText('+237 6XX XXX XXX'), '+237699000002')
  await user.click(screen.getByRole('button', { name: /suivant/i }))
}

async function goToPaymentStep(user: ReturnType<typeof userEvent.setup>) {
  vi.mocked(simulateTransfer).mockResolvedValue({
    amount_eur: '100.00',
    fees_eur: '1.50',
    fees_percentage: '1.5',
    net_eur: '98.50',
    exchange_rate: '655.957',
    amount_xaf: '64611.76',
  })
  vi.mocked(initiateTransfer).mockResolvedValue({
    transaction_id: 'txn-abc',
    status: 'PROCESSING',
    client_secret: 'cs_test_123',
  })

  await goToAmountStep(user)
  await user.type(screen.getByLabelText('Montant à envoyer en euros'), '100')
  await vi.advanceTimersByTimeAsync(300)
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /confirmer le transfert/i })).toBeEnabled()
  )
  await user.click(screen.getByRole('button', { name: /confirmer le transfert/i }))
  await waitFor(() => expect(screen.getByRole('button', { name: /^payer$/i })).toBeInTheDocument())
}

describe('TransferStepper — étape simulation (partie 3/4)', () => {
  it("appelle le VRAI endpoint de simulation (débounce 300ms) plutôt qu'un calcul local", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null })
    vi.mocked(simulateTransfer).mockResolvedValue({
      amount_eur: '100.00',
      fees_eur: '1.50',
      fees_percentage: '1.5',
      net_eur: '98.50',
      exchange_rate: '655.957',
      // Valeur volontairement DIFFÉRENTE de ce que donnerait le calcul local
      // (lib/amountConverter) pour prouver que c'est bien la réponse API qui
      // est affichée, pas un recalcul côté client.
      amount_xaf: '70000.00',
    })

    await goToAmountStep(user)

    const input = screen.getByLabelText('Montant à envoyer en euros')
    await user.type(input, '100')

    await vi.advanceTimersByTimeAsync(300)

    await waitFor(() => expect(simulateTransfer).toHaveBeenCalledWith(100))

    await waitFor(() => {
      expect(screen.getByTestId('amount-conversion-result')).toHaveTextContent(/70.?000/)
    })

    vi.useRealTimers()
  }, 15000)

  it("n'appelle pas la simulation avant la fin du débounce", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null })
    vi.mocked(simulateTransfer).mockResolvedValue({
      amount_eur: '50.00',
      fees_eur: '0.75',
      fees_percentage: '1.5',
      net_eur: '49.25',
      exchange_rate: '655.957',
      amount_xaf: '32306.75',
    })

    await goToAmountStep(user)
    await user.type(screen.getByLabelText('Montant à envoyer en euros'), '50')

    await vi.advanceTimersByTimeAsync(100)
    expect(simulateTransfer).not.toHaveBeenCalled()

    vi.useRealTimers()
  }, 15000)
})

describe('TransferStepper — redirection auto post-paiement', () => {
  it('redirige automatiquement vers /transfer/{id} après le délai de 3s', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null })
    confirmCardPayment.mockResolvedValue({ paymentIntent: { status: 'succeeded' } })

    await goToPaymentStep(user)
    await user.click(screen.getByRole('button', { name: /^payer$/i }))

    await waitFor(() => expect(screen.getByText(/paiement confirmé/i)).toBeInTheDocument())
    expect(routerPush).not.toHaveBeenCalled()

    // Un seul setInterval côté composant (pas une chaîne de setTimeout
    // reprogrammés depuis un effet) : un unique avancement de 3000ms suffit.
    await vi.advanceTimersByTimeAsync(3000)

    expect(routerPush).toHaveBeenCalledWith('/transfer/txn-abc')

    vi.useRealTimers()
  }, 15000)

  it("le lien \"Voir le suivi maintenant\" redirige immédiatement sans attendre le décompte", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null })
    confirmCardPayment.mockResolvedValue({ paymentIntent: { status: 'succeeded' } })

    await goToPaymentStep(user)
    await user.click(screen.getByRole('button', { name: /^payer$/i }))

    await waitFor(() => expect(screen.getByText(/paiement confirmé/i)).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /voir le suivi maintenant/i }))

    expect(routerPush).toHaveBeenCalledWith('/transfer/txn-abc')
    expect(routerPush).toHaveBeenCalledTimes(1)

    vi.useRealTimers()
  }, 15000)
})

describe('TransferStepper — le bouton Payer ne reste jamais bloqué en cas d\'erreur', () => {
  it('se débloque et affiche un message après un refus Stripe (error retourné par confirmCardPayment)', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null })
    confirmCardPayment.mockResolvedValue({ error: { message: 'Carte refusée par la banque.' } })

    await goToPaymentStep(user)
    const payButton = screen.getByRole('button', { name: /^payer$/i })
    await user.click(payButton)

    await waitFor(() => expect(screen.getByText('Carte refusée par la banque.')).toBeInTheDocument())
    expect(payButton).not.toBeDisabled()
    expect(payButton).toHaveTextContent(/^payer$/i)

    vi.useRealTimers()
  }, 15000)

  it("se débloque et affiche un message après une exception inattendue (ex: IntegrationError Stripe)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null })
    confirmCardPayment.mockRejectedValue(
      new Error('We could not retrieve data from the specified Element.')
    )

    await goToPaymentStep(user)
    const payButton = screen.getByRole('button', { name: /^payer$/i })
    await user.click(payButton)

    await waitFor(() =>
      expect(
        screen.getByText('We could not retrieve data from the specified Element.')
      ).toBeInTheDocument()
    )
    expect(payButton).not.toBeDisabled()
    expect(payButton).toHaveTextContent(/^payer$/i)

    vi.useRealTimers()
  }, 15000)
})

describe('TransferStepper — carnet de contacts', () => {
  function savedBeneficiary(overrides: Partial<SavedBeneficiary> = {}): SavedBeneficiary {
    return {
      id: 'ben-1',
      beneficiary_name: 'Alice Ngo',
      beneficiary_country: 'CM',
      momo_number: '+237655000089',
      operator: 'ORANGE_MONEY',
      created_at: '2026-01-01T10:00:00Z',
      last_used_at: null,
      ...overrides,
    }
  }

  it('sélectionner un bénéficiaire enregistré préremplit le formulaire', async () => {
    vi.mocked(getSavedBeneficiaries).mockResolvedValue([savedBeneficiary()])
    const user = userEvent.setup()

    render(<TransferStepper />)

    await waitFor(() => expect(screen.getByText('Alice Ngo')).toBeInTheDocument())
    await user.click(screen.getByText('Alice Ngo'))

    expect(screen.getByPlaceholderText('Jean-Pierre Mbarga')).toHaveValue('Alice Ngo')
    expect(screen.getByPlaceholderText('+237 6XX XXX XXX')).toHaveValue('+237655000089')
    expect(screen.getByRole('radio', { name: /orange money/i })).toBeChecked()
  })

  it('la case "Enregistrer ce bénéficiaire" cochée déclenche l\'enregistrement à la confirmation', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null })
    vi.mocked(simulateTransfer).mockResolvedValue({
      amount_eur: '100.00',
      fees_eur: '1.50',
      fees_percentage: '1.5',
      net_eur: '98.50',
      exchange_rate: '655.957',
      amount_xaf: '64611.76',
    })
    vi.mocked(initiateTransfer).mockResolvedValue({
      transaction_id: 'txn-abc',
      status: 'PROCESSING',
      client_secret: 'cs_test_123',
    })
    vi.mocked(saveBeneficiary).mockResolvedValue(savedBeneficiary({ id: 'ben-new' }))

    render(<TransferStepper />)
    await user.type(screen.getByPlaceholderText('Jean-Pierre Mbarga'), 'Jean Mbarga')
    await user.type(screen.getByPlaceholderText('+237 6XX XXX XXX'), '+237699000002')
    await user.click(screen.getByLabelText(/enregistrer ce bénéficiaire/i))
    await user.click(screen.getByRole('button', { name: /suivant/i }))

    await user.type(screen.getByLabelText('Montant à envoyer en euros'), '100')
    await vi.advanceTimersByTimeAsync(300)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /confirmer le transfert/i })).toBeEnabled()
    )
    await user.click(screen.getByRole('button', { name: /confirmer le transfert/i }))

    await waitFor(() =>
      expect(saveBeneficiary).toHaveBeenCalledWith({
        beneficiary_name: 'Jean Mbarga',
        beneficiary_country: 'CM',
        momo_number: '+237699000002',
        // +237699… -> préfixe 69x -> détecté Orange automatiquement (aucune
        // sélection manuelle de l'opérateur dans ce test).
        operator: 'ORANGE_MONEY',
      })
    )

    vi.useRealTimers()
  }, 15000)

  it("sans cocher la case, aucun appel à l'enregistrement du bénéficiaire n'est déclenché", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ delay: null })
    vi.mocked(simulateTransfer).mockResolvedValue({
      amount_eur: '100.00',
      fees_eur: '1.50',
      fees_percentage: '1.5',
      net_eur: '98.50',
      exchange_rate: '655.957',
      amount_xaf: '64611.76',
    })
    vi.mocked(initiateTransfer).mockResolvedValue({
      transaction_id: 'txn-abc',
      status: 'PROCESSING',
      client_secret: 'cs_test_123',
    })

    await goToPaymentStep(user)

    expect(saveBeneficiary).not.toHaveBeenCalled()

    vi.useRealTimers()
  }, 15000)
})
