import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import Home from './page'
import { getLoggedInUser } from '@/lib/actions/user.actions'
import { getKYCStatus } from '@/lib/actions/kyc.actions'

const redirectMock = vi.fn()
vi.mock('next/navigation', () => ({
  redirect: (path: string) => redirectMock(path),
}))

vi.mock('@/lib/actions/user.actions', () => ({
  getLoggedInUser: vi.fn(),
}))
vi.mock('@/lib/actions/kyc.actions', () => ({
  getKYCStatus: vi.fn(),
}))
vi.mock('@/components/Dashboard', () => ({
  default: ({ firstName }: { firstName: string }) => (
    <div data-testid="dashboard">Dashboard de {firstName}</div>
  ),
}))
vi.mock('@/components/LandingPage', () => ({
  default: () => <div data-testid="landing-page">Landing</div>,
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
    is_kyc_verified: false,
    is_2fa_enabled: false,
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

describe('Home ("/") — le lien "Accueil" reste fonctionnel pour un admin', () => {
  it("affiche le dashboard personnel pour un admin (is_staff + 2FA) qui revient sur '/', sans jamais rediriger vers /admin", async () => {
    vi.mocked(getLoggedInUser).mockResolvedValue(
      makeUser({ is_staff: true, is_2fa_enabled: true, firstName: 'Alice' })
    )
    vi.mocked(getKYCStatus).mockResolvedValue({ status: null, document: null })

    render(await Home())

    expect(await screen.findByTestId('dashboard')).toBeInTheDocument()
    expect(redirectMock).not.toHaveBeenCalled()
  })

  it('affiche le dashboard personnel pour un utilisateur non-staff (comportement inchangé)', async () => {
    vi.mocked(getLoggedInUser).mockResolvedValue(makeUser({ is_staff: false }))
    vi.mocked(getKYCStatus).mockResolvedValue({ status: null, document: null })

    render(await Home())

    expect(await screen.findByTestId('dashboard')).toBeInTheDocument()
    expect(redirectMock).not.toHaveBeenCalled()
  })

  it('affiche la landing page pour un visiteur anonyme', async () => {
    vi.mocked(getLoggedInUser).mockResolvedValue(null)

    render(await Home())

    expect(screen.getByTestId('landing-page')).toBeInTheDocument()
  })
})
