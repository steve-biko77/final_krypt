import { describe, expect, it } from 'vitest'
import { cleanup, renderWithProviders as render, screen, waitFor } from '@/lib/test-utils'
import userEvent from '@testing-library/user-event'
import { afterEach } from 'vitest'
import AmountConverter from './AmountConverter'
import { convertEurToXafLocal, formatXaf } from '@/lib/amountConverter'

afterEach(() => cleanup())

// toLocaleString('fr-FR') utilise un espace fine insécable (U+202F) comme
// séparateur de milliers, invisible à l'affichage des erreurs de test — on
// normalise tout espace Unicode avant comparaison pour rester robuste face
// aux variations d'ICU entre environnements.
function normalizeSpaces(value: string): string {
  return value.replace(/\s/gu, ' ')
}

describe('AmountConverter', () => {
  it('calcule 100 EUR -> le bon montant FCFA avec frais 1.5% appliqués (défaut)', () => {
    render(<AmountConverter initialAmountEur={100} />)

    const expected = normalizeSpaces(formatXaf(convertEurToXafLocal(100).amountXaf))
    const actual = normalizeSpaces(
      screen.getByTestId('amount-conversion-result').textContent ?? ''
    )
    expect(actual).toBe(expected)
  })

  it('recalcule en temps réel à chaque frappe (pas de debounce)', async () => {
    const user = userEvent.setup()
    render(<AmountConverter initialAmountEur={100} />)

    const input = screen.getByLabelText('Montant en euros')
    await user.clear(input)
    await user.type(input, '200')

    // Le résultat compte progressivement vers la nouvelle valeur (correctif
    // Framer Motion) plutôt que de sauter instantanément — on attend la valeur
    // finale plutôt que de vérifier une frappe intermédiaire de l'animation.
    const expected = normalizeSpaces(formatXaf(convertEurToXafLocal(200).amountXaf))
    await waitFor(() => {
      const actual = normalizeSpaces(
        screen.getByTestId('amount-conversion-result').textContent ?? ''
      )
      expect(actual).toBe(expected)
    })
  })

  it('déclenche onSend avec le montant courant au clic sur le CTA', async () => {
    const user = userEvent.setup()
    let sent: number | null = null
    render(<AmountConverter initialAmountEur={50} onSend={(amount) => (sent = amount)} />)

    await user.click(screen.getByRole('button', { name: /envoyer maintenant/i }))

    expect(sent).toBe(50)
  })
})
