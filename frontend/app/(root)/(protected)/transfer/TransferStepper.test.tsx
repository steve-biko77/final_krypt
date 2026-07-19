import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TransferStepper from './TransferStepper'
import { initiateTransfer, simulateTransfer } from '@/lib/actions/transfer.actions'

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
  CardElement: () => null,
  useElements: () => ({ getElement: () => ({}) }),
  useStripe: () => ({ confirmCardPayment }),
}))

vi.mock('@/lib/actions/transfer.actions', () => ({
  simulateTransfer: vi.fn(),
  initiateTransfer: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
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
