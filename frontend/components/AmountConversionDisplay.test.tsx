import { describe, expect, it, vi, afterEach } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AmountConversionDisplay from './AmountConversionDisplay'
import { formatXaf } from '@/lib/amountConverter'

afterEach(() => cleanup())

function normalizeSpaces(value: string): string {
  return value.replace(/\s/gu, ' ')
}

describe('AmountConversionDisplay', () => {
  it("affiche exactement le montant XAF fourni en prop, sans effectuer aucun calcul", () => {
    render(
      <AmountConversionDisplay
        amountEurValue="100"
        onAmountEurChange={() => {}}
        amountXaf={64611.7645}
      />
    )

    const expected = normalizeSpaces(formatXaf(64611.7645))
    const actual = normalizeSpaces(
      screen.getByTestId('amount-conversion-result').textContent ?? ''
    )
    expect(actual).toBe(expected)
  })

  it("affiche un état de chargement (et pas le dernier montant) quand isLoading est vrai", () => {
    render(
      <AmountConversionDisplay
        amountEurValue="100"
        onAmountEurChange={() => {}}
        amountXaf={64611.76}
        isLoading
      />
    )

    expect(screen.getByTestId('amount-conversion-loading')).toBeInTheDocument()
    expect(screen.queryByTestId('amount-conversion-result')).not.toBeInTheDocument()
  })

  it('affiche un placeholder neutre quand amountXaf est null (aucun résultat encore disponible)', () => {
    render(
      <AmountConversionDisplay amountEurValue="" onAmountEurChange={() => {}} amountXaf={null} />
    )

    expect(screen.getByTestId('amount-conversion-result')).toHaveTextContent('—')
  })

  it("est un input contrôlé : reflète la prop et remonte le texte brut saisi sans le transformer", async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <AmountConversionDisplay
        amountEurValue="42"
        onAmountEurChange={onChange}
        amountXaf={27564.6}
      />
    )

    const input = screen.getByLabelText('Montant en euros') as HTMLInputElement
    expect(input.value).toBe('42')

    await user.type(input, '5')

    // Contrôlé par la prop (amountEurValue reste "42" dans ce test) : chaque
    // frappe remonte le texte concaténé brut tel quel, sans parsing/calcul —
    // la responsabilité du calcul appartient exclusivement à l'appelant.
    expect(onChange).toHaveBeenCalledWith('425')
  })

  it('accepte des libellés personnalisés (from/to) pour être réutilisé par le tunnel de transfert', () => {
    render(
      <AmountConversionDisplay
        amountEurValue="10"
        onAmountEurChange={() => {}}
        amountXaf={6559.57}
        fromLabel="Montant à envoyer"
        toLabel="Le destinataire recevra"
      />
    )

    expect(screen.getByText('Montant à envoyer')).toBeInTheDocument()
    expect(screen.getByText('Le destinataire recevra')).toBeInTheDocument()
  })
})
