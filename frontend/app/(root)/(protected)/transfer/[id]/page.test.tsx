import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, renderWithProviders as render, screen, waitFor } from '@/lib/test-utils'
import userEvent from '@testing-library/user-event'
import TransferTrackingPage from './page'
import {
  downloadTransferReceipt,
  getTransferStatus,
  type TransferStatus,
} from '@/lib/actions/transfer.actions'

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'txn-1' }),
}))

vi.mock('@/lib/actions/transfer.actions', () => ({
  getTransferStatus: vi.fn(),
  cancelTransfer: vi.fn(),
  downloadTransferReceipt: vi.fn(),
}))

function transferStatus(overrides: Partial<TransferStatus> = {}): TransferStatus {
  return {
    transaction_id: 'txn-1',
    status: 'ESCROWED',
    amount_eur: '100.00',
    fees_eur: '1.50',
    amount_xaf: '64611.76',
    beneficiary_name: 'Jean Mbarga',
    beneficiary_country: 'CM',
    operator: 'MTN_MOMO',
    escrow_tx_hash: '0xdeadbeef',
    payout_reference: null,
    created_at: '2026-01-01T10:00:00Z',
    updated_at: '2026-01-01T10:05:00Z',
    escrowed_at: '2026-01-01T10:05:00Z',
    batch_id: null,
    batch_tx_hash: null,
    ...overrides,
  }
}

beforeEach(() => {
  // jsdom n'implémente pas URL.createObjectURL/revokeObjectURL — stubs
  // minimaux pour laisser le chemin de téléchargement (Blob + <a download>)
  // s'exécuter sans lever, comme un vrai navigateur le ferait.
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: vi.fn(() => 'blob:mock-url'),
    revokeObjectURL: vi.fn(),
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('TransferTrackingPage — bouton "Télécharger le reçu"', () => {
  it("n'apparaît pas pour un transfert non livré", async () => {
    vi.mocked(getTransferStatus).mockResolvedValue(transferStatus({ status: 'ESCROWED' }))

    render(<TransferTrackingPage />)

    await waitFor(() => expect(screen.getByText('Jean Mbarga')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /télécharger le reçu/i })).not.toBeInTheDocument()
  })

  it('apparaît pour un transfert livré et déclenche le téléchargement', async () => {
    vi.mocked(getTransferStatus).mockResolvedValue(transferStatus({ status: 'DELIVERED' }))
    vi.mocked(downloadTransferReceipt).mockResolvedValue({
      filename: 'recu-krypt-txn-1.pdf',
      base64: btoa('%PDF-fake-content'),
    })
    const user = userEvent.setup()

    render(<TransferTrackingPage />)

    await waitFor(() => expect(screen.getByText('Jean Mbarga')).toBeInTheDocument())
    const button = screen.getByRole('button', { name: /télécharger le reçu/i })
    await user.click(button)

    await waitFor(() => expect(downloadTransferReceipt).toHaveBeenCalledWith('txn-1'))
  })

  it("affiche une erreur claire si le téléchargement échoue, sans planter", async () => {
    vi.mocked(getTransferStatus).mockResolvedValue(transferStatus({ status: 'DELIVERED' }))
    vi.mocked(downloadTransferReceipt).mockRejectedValue(new Error('Erreur 400'))
    const user = userEvent.setup()

    render(<TransferTrackingPage />)

    await waitFor(() => expect(screen.getByText('Jean Mbarga')).toBeInTheDocument())
    const button = screen.getByRole('button', { name: /télécharger le reçu/i })
    await user.click(button)

    await waitFor(() => expect(downloadTransferReceipt).toHaveBeenCalled())
    expect(button).not.toBeDisabled()
  })
})
