import { describe, expect, it, afterEach } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import LandingPage from './LandingPage'
import { convertEurToXafLocal, formatXaf } from '@/lib/amountConverter'

afterEach(() => cleanup())

// toLocaleString('fr-FR') utilise un espace fine insécable (U+202F) comme
// séparateur de milliers — on normalise avant comparaison (voir AmountConverter.test.tsx).
function normalizeSpaces(value: string): string {
  return value.replace(/\s/gu, ' ')
}

describe('LandingPage', () => {
  it("expose l'AmountConverter sans authentification (aucun mock/contexte utilisateur requis)", () => {
    render(<LandingPage />)

    expect(screen.getByTestId('amount-converter')).toBeInTheDocument()

    const expected = normalizeSpaces(formatXaf(convertEurToXafLocal(100).amountXaf))
    const actual = normalizeSpaces(
      screen.getByTestId('amount-conversion-result').textContent ?? ''
    )
    expect(actual).toBe(expected)
  })

  it("le CTA de l'AmountConverter pointe vers /sign-up, pas vers un envoi réel", () => {
    render(<LandingPage />)

    const cta = screen.getByRole('link', { name: /créer un compte pour envoyer/i })
    expect(cta).toHaveAttribute('href', '/sign-up')
  })

  it('propose Se connecter et Créer un compte sans exiger de session', () => {
    render(<LandingPage />)

    expect(screen.getByRole('link', { name: 'Se connecter' })).toHaveAttribute('href', '/sign-in')
    expect(
      screen.getAllByRole('link', { name: /créer un compte/i })[0]
    ).toHaveAttribute('href', '/sign-up')
  })
})
