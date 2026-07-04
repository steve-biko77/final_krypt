'use server';

import { cookies } from 'next/headers';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export interface TransferSimulation {
  amount_eur: string;
  fees_eur: string;
  fees_percentage: string;
  net_eur: string;
  exchange_rate: string;
  amount_xaf: string;
}

export const simulateTransfer = async (
  amountEur: number,
): Promise<TransferSimulation> => {
  const jar = await cookies();
  const token = jar.get('krypt-access-token')?.value;
  if (!token) throw new Error('Non authentifié');

  const res = await fetch(
    `${API_BASE}/api/transfer/simulate?amount=${amountEur}`,
    {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    },
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg = (err as { error?: string; detail?: string }).error
      ?? (err as { detail?: string }).detail
      ?? `Erreur ${res.status}`;
    throw new Error(msg);
  }

  return res.json();
};

export interface InitiateTransferInput {
  beneficiary_name: string;
  beneficiary_country: string;
  momo_number: string;
  operator: 'MTN_MOMO' | 'ORANGE_MONEY';
  amount_eur: number;
}

export interface InitiateTransferResult {
  transaction_id: string;
  status: 'PROCESSING' | 'AML_PENDING_REVIEW';
  client_secret?: string;
}

export const initiateTransfer = async (
  input: InitiateTransferInput,
): Promise<InitiateTransferResult> => {
  const jar = await cookies();
  const token = jar.get('krypt-access-token')?.value;
  if (!token) throw new Error('Non authentifié');

  const res = await fetch(`${API_BASE}/api/transfer/initiate`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    cache: 'no-store',
    body: JSON.stringify(input),
  });

  // 201 = paiement à confirmer, 202 = en révision de conformité.
  if (res.status === 201 || res.status === 202) {
    return res.json();
  }

  // 403 = bloqué (AML) ou KYC — ne jamais exposer les détails de scoring.
  if (res.status === 403) {
    throw new Error(
      "Ce transfert n'a pas pu être autorisé après nos vérifications de conformité.",
    );
  }

  const err = await res.json().catch(() => ({}));
  const msg = (err as { error?: string; detail?: string }).error
    ?? (err as { detail?: string }).detail
    ?? `Erreur ${res.status}`;
  throw new Error(msg);
};
