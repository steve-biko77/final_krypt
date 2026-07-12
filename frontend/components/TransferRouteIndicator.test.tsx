import { describe, expect, it, afterEach } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import TransferRouteIndicator from './TransferRouteIndicator'
import type { TimelineStep } from '@/lib/transferTimeline'

afterEach(() => cleanup())

const steps: TimelineStep[] = [
  { key: 'sent', label: 'Envoyé', description: '', status: 'done' },
  { key: 'compliance', label: 'Conformité', description: '', status: 'active' },
  { key: 'payment', label: 'Paiement', description: '', status: 'pending' },
  { key: 'payout', label: 'Envoi', description: '', status: 'pending' },
  { key: 'delivered', label: 'Livré', description: '', status: 'pending' },
]

describe('TransferRouteIndicator', () => {
  it("s'affiche sans erreur en mode mini, sans labels origine/destination", () => {
    render(<TransferRouteIndicator steps={steps} mode="mini" />)

    const el = screen.getByTestId('transfer-route-indicator')
    expect(el).toHaveAttribute('data-mode', 'mini')
    expect(screen.queryByText('Vous')).not.toBeInTheDocument()
  })

  it("s'affiche sans erreur en mode full, avec labels origine/destination", () => {
    render(
      <TransferRouteIndicator
        steps={steps}
        mode="full"
        originLabel="Vous"
        destinationLabel="Jean, Yaoundé"
      />
    )

    const el = screen.getByTestId('transfer-route-indicator')
    expect(el).toHaveAttribute('data-mode', 'full')
    expect(screen.getByText('Vous')).toBeInTheDocument()
    expect(screen.getByText('Jean, Yaoundé')).toBeInTheDocument()
  })

  it('mode="full" par défaut', () => {
    render(<TransferRouteIndicator steps={steps} />)
    expect(screen.getByTestId('transfer-route-indicator')).toHaveAttribute('data-mode', 'full')
  })
})
