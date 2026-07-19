import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AMLHardBlockFreezeDialog from './AMLHardBlockFreezeDialog'
import { freezeAccount } from '@/lib/actions/admin-aml.actions'

// Radix Dialog s'appuie sur l'API Pointer Events, absente de jsdom.
beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false
  Element.prototype.setPointerCapture ??= () => {}
  Element.prototype.releasePointerCapture ??= () => {}
  Element.prototype.scrollIntoView ??= () => {}
})

const routerRefresh = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: routerRefresh }),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('@/lib/actions/admin-aml.actions', () => ({
  freezeAccount: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AMLHardBlockFreezeDialog — gel de compte protégé par confirmation', () => {
  it("n'appelle jamais freezeAccount avant la confirmation dans le Dialog", async () => {
    const user = userEvent.setup()
    const onFrozen = vi.fn()
    render(
      <AMLHardBlockFreezeDialog
        transferId="txn-hard-block-1"
        senderLabel="suspect@example.com"
        isFrozen={false}
        onFrozen={onFrozen}
      />
    )

    // Ouvrir le Dialog ne doit déclencher AUCUN appel API — seule la
    // confirmation explicite à l'intérieur du Dialog le fait.
    await user.click(screen.getByRole('button', { name: /geler le compte/i }))

    expect(
      await screen.findByRole('heading', { name: /geler le compte de l.émetteur/i })
    ).toBeInTheDocument()
    expect(screen.getByText(/suspect@example\.com/)).toBeInTheDocument()
    expect(freezeAccount).not.toHaveBeenCalled()
    expect(onFrozen).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: /annuler/i }))
    expect(freezeAccount).not.toHaveBeenCalled()
  })

  it('appelle freezeAccount uniquement après confirmation, puis notifie et ferme le Dialog', async () => {
    vi.mocked(freezeAccount).mockResolvedValue({
      transaction_id: 'txn-hard-block-1',
      user_id: 'user-1',
      account_frozen: true,
      polygonscan_url: null,
    })
    const user = userEvent.setup()
    const onFrozen = vi.fn()
    render(
      <AMLHardBlockFreezeDialog
        transferId="txn-hard-block-1"
        senderLabel="suspect@example.com"
        isFrozen={false}
        onFrozen={onFrozen}
      />
    )

    await user.click(screen.getByRole('button', { name: /geler le compte/i }))
    await screen.findByRole('heading', { name: /geler le compte de l.émetteur/i })

    await user.click(screen.getByRole('button', { name: /confirmer le gel du compte/i }))

    await waitFor(() => expect(freezeAccount).toHaveBeenCalledWith('txn-hard-block-1'))
    await waitFor(() => expect(onFrozen).toHaveBeenCalled())
    await waitFor(() =>
      expect(
        screen.queryByRole('heading', { name: /geler le compte de l.émetteur/i })
      ).not.toBeInTheDocument()
    )
  })
})
