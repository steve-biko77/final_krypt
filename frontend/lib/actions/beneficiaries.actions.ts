'use server';

import { cookies } from 'next/headers';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export interface SavedBeneficiary {
  id: string;
  beneficiary_name: string;
  beneficiary_country: string;
  momo_number: string;
  operator: 'MTN_MOMO' | 'ORANGE_MONEY';
  created_at: string;
  last_used_at: string | null;
}

export interface SaveBeneficiaryInput {
  beneficiary_name: string;
  beneficiary_country: string;
  momo_number: string;
  operator: 'MTN_MOMO' | 'ORANGE_MONEY';
}

// Carnet de contacts (tunnel de transfert) — échoue silencieusement (liste
// vide) plutôt que de faire planter l'étape Destinataire, même idiome que
// getMyTransfers : ce n'est jamais bloquant pour le tunnel.
export const getSavedBeneficiaries = async (): Promise<SavedBeneficiary[]> => {
  try {
    const jar = await cookies();
    const token = jar.get('krypt-access-token')?.value;
    if (!token) return [];

    const res = await fetch(`${API_BASE}/api/transfer/beneficiaries`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    });
    if (!res.ok) return [];

    return await res.json();
  } catch {
    return [];
  }
};

// Opt-in explicite uniquement — appelé uniquement quand l'utilisateur a coché
// "Enregistrer ce bénéficiaire" (jamais automatiquement).
export const saveBeneficiary = async (
  input: SaveBeneficiaryInput,
): Promise<SavedBeneficiary> => {
  const jar = await cookies();
  const token = jar.get('krypt-access-token')?.value;
  if (!token) throw new Error('Non authentifié');

  const res = await fetch(`${API_BASE}/api/transfer/beneficiaries`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    cache: 'no-store',
    body: JSON.stringify(input),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg = (err as { error?: string; detail?: string }).error
      ?? (err as { detail?: string }).detail
      ?? `Erreur ${res.status}`;
    throw new Error(msg);
  }

  return res.json();
};

export const deleteBeneficiary = async (id: string): Promise<void> => {
  const jar = await cookies();
  const token = jar.get('krypt-access-token')?.value;
  if (!token) throw new Error('Non authentifié');

  const res = await fetch(`${API_BASE}/api/transfer/beneficiaries/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg = (err as { error?: string; detail?: string }).error
      ?? (err as { detail?: string }).detail
      ?? `Erreur ${res.status}`;
    throw new Error(msg);
  }
};
