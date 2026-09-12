/** Pays bénéficiaires supportés (mêmes codes que TransferStepper). */
const COUNTRY_LABELS: Record<string, string> = {
  CM: 'Cameroun',
  FR: 'France',
  SN: 'Sénégal',
  CI: "Côte d'Ivoire",
}

export function countryLabel(code: string): string {
  return COUNTRY_LABELS[code] ?? code
}
