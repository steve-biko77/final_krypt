/**
 * Masque un numéro Mobile Money pour affichage dans le carnet de contacts —
 * garde le préfixe international et les 2 premiers chiffres du numéro local
 * visibles, masque le milieu, révèle les 2 derniers chiffres.
 *
 * Ex: "+237699000002" -> "+237 69• ••• •02"
 */
export function maskMobileNumber(rawNumber: string): string {
  const digits = rawNumber.replace(/\D/g, '')
  const hasCountryCode = digits.startsWith('237') && digits.length > 9
  const prefix = hasCountryCode ? '+237 ' : ''
  const local = hasCountryCode ? digits.slice(3) : digits

  if (local.length !== 9) {
    // Format non standard (import manuel, etc.) — repli minimal : 2 premiers
    // et 2 derniers chiffres visibles, le reste masqué.
    if (local.length <= 4) return rawNumber
    const visibleStart = local.slice(0, 2)
    const visibleEnd = local.slice(-2)
    const masked = '•'.repeat(local.length - 4)
    return `${prefix}${visibleStart}${masked}${visibleEnd}`
  }

  const g1 = local.slice(0, 3)
  const g3 = local.slice(6, 9)

  return `${prefix}${g1.slice(0, 2)}• ••• •${g3.slice(1)}`
}
