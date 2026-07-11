'use server';

import { cookies } from 'next/headers';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export interface AdminAMLPendingItem {
  transfer_id: string;
  tag_ml_score: number;
  xgboost_score: number;
  ofac_match: boolean;
  triggered_rules: string[];
  created_at: string | null;
}

export interface AdminAMLListResponse {
  count: number;
  results: AdminAMLPendingItem[];
}

export interface AdminAMLTransactionHistoryItem {
  transaction_id: string;
  status: string;
  amount_eur: string;
  beneficiary_name: string;
  created_at: string;
}

export interface AdminAMLDetail {
  transaction_id: string;
  status: string;
  amount_eur: string;
  amount_xaf: string;
  beneficiary_name: string;
  beneficiary_country: string;
  sender_email: string | null;
  sender_is_kyc_verified: boolean | null;
  aml: {
    tag_ml_score: number;
    tag_ml_score_label: string;
    xgboost_score: number;
    ofac_match: boolean;
    ofac_details: Record<string, unknown> | null;
    triggered_rules: string[];
    is_new_beneficiary: boolean;
    sender_tx_count_30d: number;
  } | null;
  sender_transaction_history: AdminAMLTransactionHistoryItem[];
  // Uniquement présent sur le détail escaladé (GET /escalated/{id}).
  escalation_comment?: string | null;
  escalated_by?: string | null;
  escalated_at?: string | null;
}

export interface AdminAMLDecisionResult {
  transaction_id: string;
  status: string;
  polygonscan_url: string | null;
}

export interface AdminAMLHistoryItem {
  id: string;
  transaction_id: string;
  action: string;
  motif: string;
  tx_hash: string | null;
  polygonscan_url: string | null;
  created_at: string;
}

export interface AdminAMLHistoryResponse {
  count: number;
  results: AdminAMLHistoryItem[];
}

async function getToken(): Promise<string> {
  const jar = await cookies();
  const token = jar.get('krypt-access-token')?.value;
  if (!token) throw new Error('Non authentifié');
  return token;
}

async function authedFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
    cache: 'no-store',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg = (err as { reason?: string; error?: string }).reason
      ?? (err as { error?: string }).error
      ?? `Erreur ${res.status}`;
    throw new Error(msg);
  }

  return res.json();
}

export const getAdminAMLPending = async (): Promise<AdminAMLListResponse> =>
  authedFetch('/api/admin/aml/pending');

export const getAdminAMLDetail = async (id: string): Promise<AdminAMLDetail> =>
  authedFetch(`/api/admin/aml/${id}`);

export const requestAMLDocs = async (
  id: string,
): Promise<{ transaction_id: string; status: string }> =>
  authedFetch(`/api/admin/aml/${id}/request-docs`, { method: 'POST' });

export const decideAMLReview = async (
  id: string,
  action: 'approve' | 'reject' | 'escalate',
  motif: string,
): Promise<AdminAMLDecisionResult> =>
  authedFetch(`/api/admin/aml/${id}/decide`, {
    method: 'PATCH',
    body: JSON.stringify({ action, motif }),
  });

export const getAdminAMLEscalated = async (): Promise<AdminAMLListResponse> =>
  authedFetch('/api/admin/aml/escalated');

export const getAdminAMLEscalatedDetail = async (id: string): Promise<AdminAMLDetail> =>
  authedFetch(`/api/admin/aml/escalated/${id}`);

export const decideAMLEscalatedReview = async (
  id: string,
  action: 'approve' | 'reject',
  motif: string,
): Promise<AdminAMLDecisionResult> =>
  authedFetch(`/api/admin/aml/escalated/${id}/decide`, {
    method: 'PATCH',
    body: JSON.stringify({ action, motif }),
  });

export const getAdminAMLHistory = async (
  actionFilter?: string,
): Promise<AdminAMLHistoryResponse> => {
  const qs = actionFilter ? `?action=${encodeURIComponent(actionFilter)}` : '';
  return authedFetch(`/api/admin/aml/history${qs}`);
};
