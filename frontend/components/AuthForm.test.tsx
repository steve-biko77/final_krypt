import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AuthForm from './AuthForm'
import { completeTwoFactorSignIn, signIn } from '@/lib/actions/user.actions'

const routerPush = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: routerPush }),
}))

vi.mock('@/lib/actions/user.actions', () => ({
  signIn: vi.fn(),
  signUp: vi.fn(),
  completeTwoFactorSignIn: vi.fn(),
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

async function submitSignIn(user: ReturnType<typeof userEvent.setup>) {
  render(<AuthForm type="sign-in" />)
  // getByLabelText n'est pas fiable ici : FormItem (components/ui/form.tsx)
  // génère son id via useId(), qui résout à la chaîne littérale "undefined"
  // dans cet environnement de test — les deux champs du formulaire finissent
  // avec le même id="undefined-form-item" (bug préexistant, hors périmètre
  // de cette tâche). On cible donc les champs par leur placeholder, comme
  // TransferStepper.test.tsx le fait déjà pour la même raison.
  await user.type(screen.getByPlaceholderText('votre@email.com'), 'user@test.com')
  await user.type(screen.getByPlaceholderText('8 caractères minimum'), 'password123')
  await user.click(screen.getByRole('button', { name: /se connecter/i }))
}

describe('AuthForm — redirection post-connexion (tableau de bord admin)', () => {
  it("redirige un utilisateur non-staff vers '/' (comportement inchangé)", async () => {
    vi.mocked(signIn).mockResolvedValue({
      requires_2fa: false,
      user: makeUser({ is_staff: false }),
    })
    const user = userEvent.setup()

    await submitSignIn(user)

    await waitFor(() => expect(routerPush).toHaveBeenCalledWith('/'))
    expect(routerPush).not.toHaveBeenCalledWith('/admin')
  })

  it("redirige un admin SANS 2FA activée vers '/', jamais vers /admin (éviterait un aller-retour 403)", async () => {
    vi.mocked(signIn).mockResolvedValue({
      requires_2fa: false,
      user: makeUser({ is_staff: true, is_2fa_enabled: false }),
    })
    const user = userEvent.setup()

    await submitSignIn(user)

    await waitFor(() => expect(routerPush).toHaveBeenCalledWith('/'))
    expect(routerPush).not.toHaveBeenCalledWith('/admin')
  })

  it('redirige un admin avec 2FA activée vers /admin après validation du code TOTP', async () => {
    vi.mocked(signIn).mockResolvedValue({ requires_2fa: true, pre_auth_token: 'pre-auth-token' })
    vi.mocked(completeTwoFactorSignIn).mockResolvedValue(
      makeUser({ is_staff: true, is_2fa_enabled: true })
    )
    const user = userEvent.setup()

    await submitSignIn(user)

    const totpInput = await screen.findByPlaceholderText('123456')
    await user.type(totpInput, '123456')
    await user.click(screen.getByRole('button', { name: /confirmer/i }))

    await waitFor(() => expect(routerPush).toHaveBeenCalledWith('/admin'))
  })
})
