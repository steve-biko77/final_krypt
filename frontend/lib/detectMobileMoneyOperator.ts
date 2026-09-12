/**
 * Détection de l'opérateur Mobile Money camerounais à partir du préfixe du
 * numéro de téléphone saisi. Sert uniquement à PRÉ-SÉLECTIONNER l'opérateur
 * dans le tunnel de transfert — le sélecteur reste toujours visible et
 * modifiable manuellement, cette détection ne verrouille jamais le choix.
 *
 * Plages de préfixes (plan de numérotation mobile camerounais) basées sur des
 * informations publiques disponibles au moment du développement (2026). Ces
 * blocs peuvent évoluer (nouvelles attributions, portabilité du numéro) : si
 * un décalage est constaté en usage réel, mettre à jour les plages ci-dessous
 * plutôt que de faire confiance indéfiniment à ce commentaire.
 *
 * MTN Cameroun    : 67x, 650-654, 680-684
 * Orange Cameroun : 69x, 655-659, 685-689
 */

export type MobileMoneyOperator = 'MTN' | 'ORANGE'

/** Ne garde que les chiffres et retire un préfixe international 237 éventuel. */
function localDigits(rawNumber: string): string {
  const digits = rawNumber.replace(/\D/g, '')
  return digits.startsWith('237') ? digits.slice(3) : digits
}

export function detectMobileMoneyOperator(rawNumber: string): MobileMoneyOperator | null {
  const digits = localDigits(rawNumber)
  if (digits.length < 3) return null

  const twoDigitPrefix = Number(digits.slice(0, 2))
  const threeDigitPrefix = Number(digits.slice(0, 3))

  const isMtn =
    twoDigitPrefix === 67 ||
    (threeDigitPrefix >= 650 && threeDigitPrefix <= 654) ||
    (threeDigitPrefix >= 680 && threeDigitPrefix <= 684)
  if (isMtn) return 'MTN'

  const isOrange =
    twoDigitPrefix === 69 ||
    (threeDigitPrefix >= 655 && threeDigitPrefix <= 659) ||
    (threeDigitPrefix >= 685 && threeDigitPrefix <= 689)
  if (isOrange) return 'ORANGE'

  return null
}
