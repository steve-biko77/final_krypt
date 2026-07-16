import { describe, expect, it, afterEach } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import Dashboard from './Dashboard'
import type { TransferStatus } from '@/lib/actions/transfer.actions'

afterEach(() => cleanup())

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

describe('Dashboard', () => {
  it("le CTA de l'AmountConverter pointe vers /transfer (utilisateur déjà authentifié)", () => {
    render(
      <Dashboard firstName="Jean" isKycVerified kycStatus="APPROVED" transfers={[]} />
    )

    const cta = screen.getByRole('link', { name: /envoyer un transfert/i })
    expect(cta).toHaveAttribute('href', '/transfer')
  })

  it("affiche le bandeau KYC quand l'identité n'est pas vérifiée", () => {
    render(
      <Dashboard firstName="Jean" isKycVerified={false} kycStatus={null} transfers={[]} />
    )

    expect(screen.getByText(/vérification d.identité requise/i)).toBeInTheDocument()
  })

  it("masque le bandeau KYC quand l'identité est vérifiée", () => {
    render(
      <Dashboard firstName="Jean" isKycVerified kycStatus="APPROVED" transfers={[]} />
    )

    expect(screen.queryByText(/vérification d.identité requise/i)).not.toBeInTheDocument()
  })

  it("affiche un état vide avec lien vers /transfer quand il n'y a aucun transfert", () => {
    render(
      <Dashboard firstName="Jean" isKycVerified kycStatus="APPROVED" transfers={[]} />
    )

    expect(screen.getByText(/pas encore effectué de transfert/i)).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /envoyer votre premier transfert/i })
    ).toHaveAttribute('href', '/transfer')
  })

  it('affiche une route miniature (pas de badge) pour un transfert non terminal', () => {
    render(
      <Dashboard
        firstName="Jean"
        isKycVerified
        kycStatus="APPROVED"
        transfers={[transfer({ status: 'ESCROWED' })]}
      />
    )

    expect(screen.getByTestId('journey-card-route')).toBeInTheDocument()
    expect(screen.getByTestId('transfer-route-indicator')).toHaveAttribute('data-mode', 'mini')
  })

  it('affiche un badge de statut (pas de route) pour un transfert terminal', () => {
    render(
      <Dashboard
        firstName="Jean"
        isKycVerified
        kycStatus="APPROVED"
        transfers={[transfer({ status: 'DELIVERED', updated_at: '2026-01-01T11:00:00Z' })]}
      />
    )

    expect(screen.queryByTestId('journey-card-route')).not.toBeInTheDocument()
    expect(screen.getByText('Terminé')).toBeInTheDocument()
  })
})
