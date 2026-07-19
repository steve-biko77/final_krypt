import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
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
    email: 'admin@test.com',
    firstName: 'Alice',
    lastName: 'Admin',
    phone: '+33600000000',
    is_kyc_verified: true,
    is_2fa_enabled: true,
    is_staff: true,
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

describe('Sidebar — section Administration', () => {
  it('place "Vue d\'ensemble" en premier, avant Admin KYC et Console AML', () => {
    mockPathname.mockReturnValue('/')
    render(<Sidebar user={makeUser()} />)

    const adminLabels = ["Vue d'ensemble", 'Admin KYC', 'Console AML'].map((label) =>
      screen.getByText(label)
    )
    const positions = adminLabels.map(
      (el) => Array.from(document.querySelectorAll('a')).indexOf(el.closest('a')!)
    )
    expect(positions).toEqual([...positions].sort((a, b) => a - b))
    expect(positions[0]).toBeLessThan(positions[1])
    expect(positions[0]).toBeLessThan(positions[2])
  })

  it('ne marque "Vue d\'ensemble" actif que sur /admin exactement, pas sur /admin/kyc ou /admin/aml', () => {
    mockPathname.mockReturnValue('/admin/kyc')
    render(<Sidebar user={makeUser()} />)

    const overviewLink = screen.getByText("Vue d'ensemble").closest('a')
    const kycLink = screen.getByText('Admin KYC').closest('a')

    expect(overviewLink).not.toHaveClass('bg-blue-25')
    expect(kycLink).toHaveClass('bg-blue-25')
  })

  it("n'affiche pas la section Administration pour un utilisateur non-staff", () => {
    mockPathname.mockReturnValue('/')
    render(<Sidebar user={makeUser({ is_staff: false })} />)

    expect(screen.queryByText("Vue d'ensemble")).not.toBeInTheDocument()
    expect(screen.queryByText('Administration')).not.toBeInTheDocument()
  })
})
