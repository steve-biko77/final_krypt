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
