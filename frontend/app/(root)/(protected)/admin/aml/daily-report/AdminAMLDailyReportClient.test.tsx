import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AdminAMLDailyReportClient from './AdminAMLDailyReportClient'
import { archiveAdminAMLDailyReport } from '@/lib/actions/admin-aml.actions'
import type { AdminAMLDailyReport } from '@/lib/actions/admin-aml.actions'

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false
  Element.prototype.setPointerCapture ??= () => {}
  Element.prototype.releasePointerCapture ??= () => {}
  Element.prototype.scrollIntoView ??= () => {}
})

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('@/lib/actions/admin-aml.actions', () => ({
  archiveAdminAMLDailyReport: vi.fn(),
  exportAdminAMLDailyReportCSV: vi.fn(),
  getAdminAMLDailyReport: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const baseReport: AdminAMLDailyReport = {
  date: '2026-07-19',
  counts: {
    approve: 3,
    reject: 1,
    escalate: 0,
    hard_block_documented: 0,
    hard_block_frozen: 0,
    hard_block_tracfin_generated: 0,
  },
  total_decisions: 4,
  decisions: [],
}

describe('AdminAMLDailyReportClient — archivage refuse un second archivage', () => {
  it("affiche clairement le message d'erreur backend ALREADY_ARCHIVED au lieu d'échouer silencieusement", async () => {
    vi.mocked(archiveAdminAMLDailyReport).mockRejectedValue(
      new Error('Le rapport du 2026-07-19 est déjà archivé.')
    )
    const user = userEvent.setup()
    render(<AdminAMLDailyReportClient initialReport={baseReport} />)

    await user.click(screen.getByRole('button', { name: /^archiver$/i }))
    await screen.findByRole('heading', { name: /archiver le rapport du 2026-07-19/i })

    await user.click(screen.getByRole('button', { name: /confirmer l.archivage/i }))

    expect(
      await screen.findByText(/le rapport du 2026-07-19 est déjà archivé\./i)
    ).toBeInTheDocument()

    // Le Dialog reste ouvert (pas d'échec silencieux) et aucune référence
    // Polygon n'est affichée puisque l'archivage a échoué.
    expect(
      screen.getByRole('heading', { name: /archiver le rapport du 2026-07-19/i })
    ).toBeInTheDocument()
    expect(screen.queryByText(/rapport du 2026-07-19 archivé/i)).not.toBeInTheDocument()
  })
})
