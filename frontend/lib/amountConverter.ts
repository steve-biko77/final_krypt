/**
 * Refonte frontend (partie 1/4) — calcul LOCAL, instantané, pour le composant
 * signature AmountConverter (aperçu "vous envoyez / le bénéficiaire reçoit").
 *
 * Volontairement distinct de la simulation serveur avec debounce du stepper de
 * transfert (TransferStepper) : ici taux et frais sont fixes, aucun appel
 * réseau — juste un aperçu immédiat, pas le montant contractuel final.
 */

export const LOCAL_EUR_TO_XAF_RATE = 655.957;
export const LOCAL_FEE_RATE = 0.015;

export interface LocalConversion {
  amountEur: number;
  feeEur: number;
  netEur: number;
  amountXaf: number;
}

export function convertEurToXafLocal(amountEur: number): LocalConversion {
  const safeAmountEur = Number.isFinite(amountEur) && amountEur > 0 ? amountEur : 0;
  const feeEur = safeAmountEur * LOCAL_FEE_RATE;
  const netEur = safeAmountEur - feeEur;
  const amountXaf = netEur * LOCAL_EUR_TO_XAF_RATE;

  return { amountEur: safeAmountEur, feeEur, netEur, amountXaf };
}

/** Même convention d'arrondi/format que le reste de l'app (TransferStepper, page de suivi) : FCFA entier, séparateur fr-FR. */
export function formatXaf(amountXaf: number): string {
  return Math.round(amountXaf).toLocaleString('fr-FR');
}
