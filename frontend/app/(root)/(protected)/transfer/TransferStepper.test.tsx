import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TransferStepper from './TransferStepper'
import { simulateTransfer } from '@/lib/actions/transfer.actions'

// Stripe.js n'a rien à faire dans ce test (on ne dépasse pas l'étape 2) —
// stubs pour éviter tout appel réseau réel/chargement de script au montage.
vi.mock('@stripe/stripe-js', () => ({ loadStripe: () => Promise.resolve(null) }))
vi.mock('@stripe/react-stripe-js', () => ({
  Elements: ({ children }: { children: React.ReactNode }) => children,
  CardElement: () => null,
  useElements: () => null,
  useStripe: () => null,
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
  })

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
  })
})
