import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import RecentTransfersList from './RecentTransfersList'
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

describe('RecentTransfersList', () => {
  it('affiche un Skeleton pendant le chargement, puis la liste une fois résolue', async () => {
    let resolvePromise: (value: { count: number; results: TransferStatus[] }) => void
    vi.mocked(getMyTransfers).mockReturnValue(
      new Promise((resolve) => {
        resolvePromise = resolve
      })
    )

    render(<RecentTransfersList />)

    expect(screen.getByLabelText('Chargement des transferts récents')).toBeInTheDocument()

    resolvePromise!({ count: 1, results: [transfer({})] })

    await waitFor(() => {
      expect(screen.getByText('Jean Mbarga')).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Chargement des transferts récents')).not.toBeInTheDocument()
  })

  it("affiche un état vide avec lien vers /transfer quand il n'y a aucun transfert", async () => {
    vi.mocked(getMyTransfers).mockResolvedValue({ count: 0, results: [] })

    render(<RecentTransfersList />)

    await waitFor(() => {
      expect(screen.getByText(/pas encore effectué de transfert/i)).toBeInTheDocument()
    })
    expect(
      screen.getByRole('link', { name: /envoyer votre premier transfert/i })
    ).toHaveAttribute('href', '/transfer')
  })

  it('affiche une route miniature (pas de badge) pour un transfert non terminal', async () => {
    vi.mocked(getMyTransfers).mockResolvedValue({
      count: 1,
      results: [transfer({ status: 'ESCROWED' })],
    })

    render(<RecentTransfersList />)

    await waitFor(() => {
      expect(screen.getByTestId('journey-card-route')).toBeInTheDocument()
    })
    expect(screen.getByTestId('transfer-route-indicator')).toHaveAttribute('data-mode', 'mini')
  })

  it('affiche un badge de statut (pas de route) pour un transfert terminal', async () => {
    vi.mocked(getMyTransfers).mockResolvedValue({
      count: 1,
      results: [transfer({ status: 'DELIVERED', updated_at: '2026-01-01T11:00:00Z' })],
    })

    render(<RecentTransfersList />)

    await waitFor(() => {
      expect(screen.getByText('Terminé')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('journey-card-route')).not.toBeInTheDocument()
  })

  it('affiche une erreur si le chargement échoue', async () => {
    vi.mocked(getMyTransfers).mockRejectedValue(new Error('Erreur réseau'))

    render(<RecentTransfersList />)

    await waitFor(() => {
      expect(screen.getByText('Erreur réseau')).toBeInTheDocument()
    })
  })
})
