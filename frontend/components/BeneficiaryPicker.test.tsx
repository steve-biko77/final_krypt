import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BeneficiaryPicker from './BeneficiaryPicker'
import {
  deleteBeneficiary,
  getSavedBeneficiaries,
  type SavedBeneficiary,
} from '@/lib/actions/beneficiaries.actions'

vi.mock('@/lib/actions/beneficiaries.actions', () => ({
  getSavedBeneficiaries: vi.fn(),
  deleteBeneficiary: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function beneficiary(overrides: Partial<SavedBeneficiary> = {}): SavedBeneficiary {
  return {
    id: 'ben-1',
    beneficiary_name: 'Jean Mbarga',
    beneficiary_country: 'CM',
    momo_number: '+237699000002',
    operator: 'MTN_MOMO',
    created_at: '2026-01-01T10:00:00Z',
    last_used_at: null,
    ...overrides,
  }
}

describe('BeneficiaryPicker', () => {
  it('affiche un Skeleton pendant le chargement', async () => {
    let resolvePromise: (value: SavedBeneficiary[]) => void
    vi.mocked(getSavedBeneficiaries).mockReturnValue(
      new Promise((resolve) => {
        resolvePromise = resolve
      })
    )

    render(<BeneficiaryPicker selectedId={null} onSelect={vi.fn()} onNew={vi.fn()} />)

    expect(screen.getByLabelText('Chargement des bénéficiaires enregistrés')).toBeInTheDocument()

    resolvePromise!([])
    await waitFor(() =>
      expect(
        screen.queryByLabelText('Chargement des bénéficiaires enregistrés')
      ).not.toBeInTheDocument()
    )
  })

  it("n'affiche rien (pas d'état vide intrusif) quand la liste est vide", async () => {
    vi.mocked(getSavedBeneficiaries).mockResolvedValue([])

    const { container } = render(
      <BeneficiaryPicker selectedId={null} onSelect={vi.fn()} onNew={vi.fn()} />
    )

    await waitFor(() => expect(container).toBeEmptyDOMElement())
  })

  it('affiche la liste avec le numéro masqué', async () => {
    vi.mocked(getSavedBeneficiaries).mockResolvedValue([beneficiary()])

    render(<BeneficiaryPicker selectedId={null} onSelect={vi.fn()} onNew={vi.fn()} />)

    await waitFor(() => expect(screen.getByText('Jean Mbarga')).toBeInTheDocument())
    expect(screen.getByText('+237 69• ••• •02')).toBeInTheDocument()
    expect(screen.queryByText('+237699000002')).not.toBeInTheDocument()
  })

  it('sélectionner un bénéficiaire appelle onSelect avec cette entrée', async () => {
    const b = beneficiary()
    vi.mocked(getSavedBeneficiaries).mockResolvedValue([b])
    const onSelect = vi.fn()
    const user = userEvent.setup()

    render(<BeneficiaryPicker selectedId={null} onSelect={onSelect} onNew={vi.fn()} />)

    await waitFor(() => expect(screen.getByText('Jean Mbarga')).toBeInTheDocument())
    await user.click(screen.getByText('Jean Mbarga'))

    expect(onSelect).toHaveBeenCalledWith(b)
  })

  it('"Nouveau bénéficiaire" n\'apparaît que si un bénéficiaire est sélectionné, et appelle onNew', async () => {
    const b = beneficiary()
    vi.mocked(getSavedBeneficiaries).mockResolvedValue([b])
    const onNew = vi.fn()
    const user = userEvent.setup()

    const { rerender } = render(
      <BeneficiaryPicker selectedId={null} onSelect={vi.fn()} onNew={onNew} />
    )
    await waitFor(() => expect(screen.getByText('Jean Mbarga')).toBeInTheDocument())
    expect(screen.queryByText('Nouveau bénéficiaire')).not.toBeInTheDocument()

    rerender(<BeneficiaryPicker selectedId="ben-1" onSelect={vi.fn()} onNew={onNew} />)
    await user.click(screen.getByText('Nouveau bénéficiaire'))

    expect(onNew).toHaveBeenCalled()
  })

  it('supprime un bénéficiaire après confirmation dans le Dialog', async () => {
    const b = beneficiary()
    vi.mocked(getSavedBeneficiaries).mockResolvedValue([b])
    vi.mocked(deleteBeneficiary).mockResolvedValue(undefined)
    const user = userEvent.setup()

    render(<BeneficiaryPicker selectedId={null} onSelect={vi.fn()} onNew={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Jean Mbarga')).toBeInTheDocument())

    await user.click(screen.getByLabelText('Supprimer Jean Mbarga'))
    expect(screen.getByText('Supprimer ce bénéficiaire ?')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^supprimer$/i }))

    await waitFor(() => expect(deleteBeneficiary).toHaveBeenCalledWith('ben-1'))
    await waitFor(() => expect(screen.queryByText('Jean Mbarga')).not.toBeInTheDocument())
  })

  it("n'appelle pas deleteBeneficiary si l'utilisateur annule", async () => {
    const b = beneficiary()
    vi.mocked(getSavedBeneficiaries).mockResolvedValue([b])
    const user = userEvent.setup()

    render(<BeneficiaryPicker selectedId={null} onSelect={vi.fn()} onNew={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Jean Mbarga')).toBeInTheDocument())

    await user.click(screen.getByLabelText('Supprimer Jean Mbarga'))
    await user.click(screen.getByRole('button', { name: /annuler/i }))

    expect(deleteBeneficiary).not.toHaveBeenCalled()
    expect(screen.getByText('Jean Mbarga')).toBeInTheDocument()
  })
})
