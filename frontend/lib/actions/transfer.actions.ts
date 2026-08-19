'use server';

import { cookies } from 'next/headers';

import type { TransactionStatus } from '@/lib/transferTimeline';

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

export interface TransferStatus {
  transaction_id: string;
  status: TransactionStatus;
  amount_eur: string;
  fees_eur: string;
  amount_xaf: string;
  beneficiary_name: string;
  beneficiary_country: string;
  operator: 'MTN_MOMO' | 'ORANGE_MONEY' | string;
  escrow_tx_hash: string | null;
  payout_reference: string | null;
  created_at: string | null;
  updated_at: string | null;
  escrowed_at: string | null;
  // KRYP-27 — lot Merkle Polygon de l'événement de livraison (null tant que non batché).
  batch_id: number | null;
  batch_tx_hash: string | null;
}

export const getTransferStatus = async (
  id: string,
): Promise<TransferStatus> => {
  const jar = await cookies();
  const token = jar.get('krypt-access-token')?.value;
  if (!token) throw new Error('Non authentifié');

  const res = await fetch(`${API_BASE}/api/transfer/${id}/status`, {
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

  return res.json();
};

export interface MyTransfersResponse {
  count: number;
  results: TransferStatus[];
}

// Refonte frontend (partie 3/4) — transferts récents de l'utilisateur connecté
// (tableau de bord). Même forme que getTransferStatus (TransferStatus),
// réutilisable telle quelle par buildTimeline côté client. Chargée sans
// interaction utilisateur au rendu du tableau de bord (comme getKYCStatus) :
// échoue silencieusement (liste vide) plutôt que de faire planter la page.
export const getMyTransfers = async (limit = 5): Promise<MyTransfersResponse> => {
  try {
    const jar = await cookies();
    const token = jar.get('krypt-access-token')?.value;
    if (!token) return { count: 0, results: [] };

    const res = await fetch(`${API_BASE}/api/transfer/mine?limit=${limit}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    });
    if (!res.ok) return { count: 0, results: [] };

    return await res.json();
  } catch {
    return { count: 0, results: [] };
  }
};

export interface CancelTransferResult {
  transaction_id: string;
  status: TransactionStatus;
}

// KRYP-28 — annulation avant confirmation Stripe (Fig. 7 : DRAFT/PENDING_AML uniquement).
export const cancelTransfer = async (
  id: string,
): Promise<CancelTransferResult> => {
  const jar = await cookies();
  const token = jar.get('krypt-access-token')?.value;
  if (!token) throw new Error('Non authentifié');

  const res = await fetch(`${API_BASE}/api/transfer/${id}/cancel`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg = (err as { reason?: string; error?: string; detail?: string }).reason
      ?? (err as { error?: string; detail?: string }).error
      ?? (err as { detail?: string }).detail
      ?? `Erreur ${res.status}`;
    throw new Error(msg);
  }

  return res.json();
};

export interface TransferReceipt {
  filename: string;
  // Contenu binaire du PDF encodé en base64 — un Server Action ne peut pas
  // retourner un Blob/ArrayBuffer directement de façon fiable ; même
  // contrainte que exportAdminAMLDailyReportCSV (qui, elle, retourne du texte
  // brut car le CSV est du texte). Décodé côté client avant de construire le
  // Blob pour le téléchargement.
  base64: string;
}

// Reçu PDF téléchargeable — uniquement disponible pour un transfert DELIVERED
// (le backend renvoie une erreur explicite sinon, propagée telle quelle).
export const downloadTransferReceipt = async (id: string): Promise<TransferReceipt> => {
  const jar = await cookies();
  const token = jar.get('krypt-access-token')?.value;
  if (!token) throw new Error('Non authentifié');

  const res = await fetch(`${API_BASE}/api/transfer/${id}/receipt`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg = (err as { detail?: string; error?: string }).detail
      ?? (err as { error?: string }).error
      ?? `Erreur ${res.status}`;
    throw new Error(msg);
  }

  const disposition = res.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : `recu-krypt-${id}.pdf`;

  const buffer = await res.arrayBuffer();
  const base64 = Buffer.from(buffer).toString('base64');

  return { filename, base64 };
};
