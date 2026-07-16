import { describe, expect, it, vi, afterEach } from 'vitest'
import { cleanup, renderWithProviders as render, screen } from '@/lib/test-utils'
import Dashboard from './Dashboard'

// RecentTransfersList (rendu par Dashboard) charge côté client — non pertinent
// pour ces tests (CTA, bandeau KYC) : on la neutralise avec une réponse vide.
vi.mock('@/lib/actions/transfer.actions', () => ({
  getMyTransfers: vi.fn().mockResolvedValue({ count: 0, results: [] }),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Dashboard', () => {
  it("le CTA de l'AmountConverter pointe vers /transfer (utilisateur déjà authentifié)", () => {
    render(<Dashboard firstName="Jean" isKycVerified kycStatus="APPROVED" />)

    const cta = screen.getByRole('link', { name: /envoyer un transfert/i })
    expect(cta).toHaveAttribute('href', '/transfer')
  })

  it("affiche le bandeau KYC quand l'identité n'est pas vérifiée", () => {
    render(<Dashboard firstName="Jean" isKycVerified={false} kycStatus={null} />)

    expect(screen.getByText(/vérification d.identité requise/i)).toBeInTheDocument()
  })

  it("masque le bandeau KYC quand l'identité est vérifiée", () => {
    render(<Dashboard firstName="Jean" isKycVerified kycStatus="APPROVED" />)

    expect(screen.queryByText(/vérification d.identité requise/i)).not.toBeInTheDocument()
  })
})
