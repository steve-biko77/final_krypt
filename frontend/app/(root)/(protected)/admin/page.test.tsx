import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import AdminDashboardPage from './page'
import { getLoggedInUser } from '@/lib/actions/user.actions'

const redirectMock = vi.fn((path: string) => {
  throw new Error(`NEXT_REDIRECT:${path}`)
})
vi.mock('next/navigation', () => ({
  redirect: (path: string) => redirectMock(path),
}))

vi.mock('@/lib/actions/user.actions', () => ({
  getLoggedInUser: vi.fn(),
}))
vi.mock('./AdminDashboardClient', () => ({
  default: () => <div data-testid="admin-dashboard-client">stats</div>,
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 'u1',
    $id: 'u1',
    email: 'admin@test.com',
    firstName: 'Alice',
    lastName: 'Admin',
    phone: '+33600000000',
    is_kyc_verified: true,
    is_2fa_enabled: false,
    is_staff: false,
    name: 'Alice Admin',
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

describe('AdminDashboardPage ("/admin") — un non-staff ne peut jamais y accéder', () => {
  it("redirige un visiteur non connecté vers '/'", async () => {
    vi.mocked(getLoggedInUser).mockResolvedValue(null)

    await expect(AdminDashboardPage()).rejects.toThrow('NEXT_REDIRECT:/')
    expect(redirectMock).toHaveBeenCalledWith('/')
  })

  it("redirige un utilisateur non-staff vers '/' plutôt que de lui montrer /admin", async () => {
    vi.mocked(getLoggedInUser).mockResolvedValue(makeUser({ is_staff: false }))

    await expect(AdminDashboardPage()).rejects.toThrow('NEXT_REDIRECT:/')
  })

  it("redirige un staff SANS 2FA activée vers '/'", async () => {
    vi.mocked(getLoggedInUser).mockResolvedValue(
      makeUser({ is_staff: true, is_2fa_enabled: false })
    )

    await expect(AdminDashboardPage()).rejects.toThrow('NEXT_REDIRECT:/')
  })

  it('affiche le tableau de bord pour un staff avec 2FA activée', async () => {
    vi.mocked(getLoggedInUser).mockResolvedValue(
      makeUser({ is_staff: true, is_2fa_enabled: true })
    )

    render(await AdminDashboardPage())

    expect(screen.getByTestId('admin-dashboard-client')).toBeInTheDocument()
  })
})
