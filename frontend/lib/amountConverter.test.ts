import { describe, expect, it } from 'vitest';
import { convertEurToXafLocal, formatXaf, LOCAL_EUR_TO_XAF_RATE, LOCAL_FEE_RATE } from './amountConverter';

describe('convertEurToXafLocal', () => {
  it('applique les frais de 1.5% avant conversion au taux fixe', () => {
    const result = convertEurToXafLocal(100);

    expect(result.feeEur).toBeCloseTo(1.5, 6);
    expect(result.netEur).toBeCloseTo(98.5, 6);
    expect(result.amountXaf).toBeCloseTo(98.5 * LOCAL_EUR_TO_XAF_RATE, 4);
  });

  it('utilise le taux et les frais fixes documentés', () => {
    expect(LOCAL_EUR_TO_XAF_RATE).toBe(655.957);
    expect(LOCAL_FEE_RATE).toBe(0.015);
  });

  it('ramène les montants invalides ou négatifs à zéro', () => {
    expect(convertEurToXafLocal(-10).amountXaf).toBe(0);
    expect(convertEurToXafLocal(NaN).amountXaf).toBe(0);
  });
});

describe('formatXaf', () => {
  it('arrondit et formate avec le séparateur fr-FR', () => {
    expect(formatXaf(64611.7645)).toBe(Math.round(64611.7645).toLocaleString('fr-FR'));
  });
});
