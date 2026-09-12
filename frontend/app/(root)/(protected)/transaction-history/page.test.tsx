import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import TransactionHistory from './page'
import { getMyTransfers } from '@/lib/actions/transfer.actions'
import type { TransferStatus } from '@/lib/actions/transfer.actions'

vi.mock('@/lib/actions/transfer.actions', () => ({
  getMyTransfers: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function transfer(overrides: Partial<TransferStatus>): TransferStatus {
  return {
    transaction_id: 'txn-1',
    status: 'DELIVERED',
    amount_eur: '100.00',
    fees_eur: '1.50',
    amount_xaf: '64611.76',
    beneficiary_name: 'Jean Mbarga',
    beneficiary_country: 'CM',
    operator: 'MTN_MOMO',
    escrow_tx_hash: '0xdeadbeef',
    payout_reference: null,
    created_at: '2026-01-01T10:00:00Z',
    updated_at: '2026-01-01T11:00:00Z',
    escrowed_at: '2026-01-01T10:05:00Z',
    batch_id: null,
    batch_tx_hash: null,
    ...overrides,
  }
}

describe('TransactionHistory — page /transaction-history (n\'est plus un stub)', () => {
  it("appelle GET /api/transfer/mine (via getMyTransfers) avec un limit généreux, et affiche les résultats", async () => {
    vi.mocked(getMyTransfers).mockResolvedValue({ count: 1, results: [transfer({})] })

    render(<TransactionHistory />)

    await waitFor(() => {
      expect(screen.getByText('Jean Mbarga')).toBeInTheDocument()
    })
    expect(getMyTransfers).toHaveBeenCalledWith(20)
    expect(screen.queryByText(/sera disponible prochainement/i)).not.toBeInTheDocument()
  })

  it("affiche un message clair quand la liste est vide", async () => {
    vi.mocked(getMyTransfers).mockResolvedValue({ count: 0, results: [] })

    render(<TransactionHistory />)

    await waitFor(() => {
      expect(screen.getByText(/pas encore effectué de transfert/i)).toBeInTheDocument()
    })
  })
})
