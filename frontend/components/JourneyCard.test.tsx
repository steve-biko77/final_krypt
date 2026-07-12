import { describe, expect, it, afterEach } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import JourneyCard from './JourneyCard'

afterEach(() => cleanup())

describe('JourneyCard', () => {
  it('affiche le bénéficiaire, la ville, le montant en euros et le badge de statut', () => {
    render(
      <JourneyCard
        beneficiaryName="Jean Mbarga"
        beneficiaryCity="Yaoundé"
        amountEur={150}
        status="active"
      />
    )

    expect(screen.getByText('Jean Mbarga')).toBeInTheDocument()
    expect(screen.getByText('Yaoundé')).toBeInTheDocument()
    expect(screen.getByText('En cours')).toBeInTheDocument()
    expect(screen.getByText('JM')).toBeInTheDocument()
  })

  it('devient un lien cliquable quand href est fourni', () => {
    render(
      <JourneyCard
        beneficiaryName="Jean Mbarga"
        beneficiaryCity="Yaoundé"
        amountEur={150}
        status="done"
        href="/transfer/abc"
      />
    )

    expect(screen.getByRole('link')).toHaveAttribute('href', '/transfer/abc')
  })
})
