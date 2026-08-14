import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import BottomNav from './BottomNav'
import Sidebar from './Sidebar'

const mockPathname = vi.fn()
vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname(),
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 'u1',
    $id: 'u1',
    email: 'user@test.com',
    firstName: 'Jean',
    lastName: 'Dupont',
    phone: '+33600000000',
    is_kyc_verified: true,
    is_2fa_enabled: true,
    is_staff: false,
    name: 'Jean Dupont',
    userId: 'u1',
    dwollaCustomerUrl: '',
    dwollaCustomerId: '',
    address1: '',
    city: '',
    state: '',
    postalCode: '',
    dateOfBirth: '',
    ssn: '',
    ...overrides,
  }
}

// jsdom n'évalue pas les media queries : comme le reste de la suite (cf.
// Sidebar.test.tsx sur bg-blue-25), on vérifie la présence des classes
// Tailwind responsables du breakpoint plutôt qu'un rendu visuel réel.
describe('BottomNav — visibilité par breakpoint (mobile uniquement)', () => {
  it('porte la classe md:hidden (visible sous md, masquée à partir de md)', () => {
    mockPathname.mockReturnValue('/')
    render(<BottomNav />)

    expect(screen.getByTestId('bottom-nav')).toHaveClass('md:hidden')
  })

  it('affiche les 4 destinations principales (Accueil, Envoyer, Historique, Sécurité), pas KYC ni les liens admin', () => {
    mockPathname.mockReturnValue('/')
    render(<BottomNav />)

    expect(screen.getByText('Accueil')).toBeInTheDocument()
    expect(screen.getByText('Envoyer')).toBeInTheDocument()
    expect(screen.getByText('Historique')).toBeInTheDocument()
    expect(screen.getByText('Sécurité')).toBeInTheDocument()

    expect(screen.queryByText('Vérification KYC')).not.toBeInTheDocument()
    expect(screen.queryByText("Vue d'ensemble")).not.toBeInTheDocument()
  })

  it('marque la destination active via aria-current="page"', () => {
    mockPathname.mockReturnValue('/transfer')
    render(<BottomNav />)

    expect(screen.getByText('Envoyer').closest('a')).toHaveAttribute('aria-current', 'page')
    expect(screen.getByText('Accueil').closest('a')).not.toHaveAttribute('aria-current')
  })

  it("la Sidebar desktop reste masquée sous md (max-md:hidden, inchangée) : les deux navigations sont bien complémentaires", () => {
    mockPathname.mockReturnValue('/')
    render(<Sidebar user={makeUser()} />)

    expect(screen.getByText('KRYPT').closest('section')).toHaveClass('max-md:hidden')
  })
})
