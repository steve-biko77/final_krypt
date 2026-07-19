import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import KYCPage from './page'
import { getKYCStatus } from '@/lib/actions/kyc.actions'

// Bug corrigé — page.tsx rendait <KYCUploadForm /> deux fois quand aucun KYC
// n'avait encore été soumis (canUpload = true via !status ET !status && !config
// simultanément). Un seul rendu doit désormais apparaître, quel que soit l'état.
vi.mock('@/lib/actions/kyc.actions', () => ({
  getKYCStatus: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('KYCPage — un seul formulaire de soumission rendu', () => {
  it("n'affiche qu'un seul formulaire quand aucun document n'a encore été soumis (status null)", async () => {
    vi.mocked(getKYCStatus).mockResolvedValue({ status: null, document: null })

    render(await KYCPage())

    expect(screen.getAllByRole('button', { name: /soumettre le document/i })).toHaveLength(1)
    expect(screen.getAllByText(/soumettre votre document/i)).toHaveLength(1)
  })

  it("n'affiche qu'un seul formulaire quand un nouveau document peut être soumis (REJECTED)", async () => {
    vi.mocked(getKYCStatus).mockResolvedValue({
      status: 'REJECTED',
      document: {
        id: 'doc-1',
        document_type: 'ID_CARD',
        status: 'REJECTED',
        file_path: 'kyc/doc-1.pdf',
        analysis_score: null,
        review_comment: 'Document illisible',
        submitted_at: '2026-01-01T10:00:00Z',
        reviewed_at: '2026-01-02T10:00:00Z',
      },
    })

    render(await KYCPage())

    expect(screen.getAllByRole('button', { name: /soumettre le document/i })).toHaveLength(1)
  })

  it("n'affiche aucun formulaire quand la soumission n'est pas autorisée (ANALYZING)", async () => {
    vi.mocked(getKYCStatus).mockResolvedValue({
      status: 'ANALYZING',
      document: {
        id: 'doc-1',
        document_type: 'ID_CARD',
        status: 'ANALYZING',
        file_path: 'kyc/doc-1.pdf',
        analysis_score: null,
        review_comment: null,
        submitted_at: '2026-01-01T10:00:00Z',
        reviewed_at: null,
      },
    })

    render(await KYCPage())

    expect(screen.queryByRole('button', { name: /soumettre le document/i })).not.toBeInTheDocument()
  })
})
