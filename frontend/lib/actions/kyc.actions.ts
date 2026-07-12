'use server';

import { cookies } from 'next/headers';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type KYCDocumentStatus =
  | 'SUBMITTED'
  | 'ANALYZING'
  | 'APPROVED'
  | 'PENDING_REVIEW'
  | 'APPROVED_MANUAL'
  | 'COMPLEMENT_REQUESTED'
  | 'REJECTED';

export interface KYCDocument {
  id: string;
  document_type: string;
  status: KYCDocumentStatus;
  file_path: string;
  analysis_score: number | null;
  review_comment: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
}

export interface KYCStatusResponse {
  status: KYCDocumentStatus | null;
  document: KYCDocument | null;
}

export interface AdminKYCListItem {
  id: string;
  user_email: string;
  user_name: string;
  document_type: string;
  status: KYCDocumentStatus;
  analysis_score: number | null;
  review_comment: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
}

export interface AdminKYCListResponse {
  count: number;
  results: AdminKYCListItem[];
}

async function getToken(): Promise<string> {
  const jar = await cookies();
  const token = jar.get('krypt-access-token')?.value;
  if (!token) throw new Error('Non authentifié');
  return token;
}

export const getKYCStatus = async (): Promise<KYCStatusResponse> => {
  try {
    const token = await getToken();
    const res = await fetch(`${API_BASE}/api/kyc/status`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    });
    if (!res.ok) return { status: null, document: null };
    return res.json();
  } catch {
    return { status: null, document: null };
  }
};

export const submitKYC = async (formData: FormData): Promise<KYCDocument> => {
  const token = await getToken();

  const file = formData.get('file') as File | null;
  const documentType = formData.get('document_type') as string;

  if (!file || file.size === 0) throw new Error('Aucun fichier sélectionné');
  if (!documentType) throw new Error('Type de document requis');

  const buffer = Buffer.from(await file.arrayBuffer());
  const apiFormData = new FormData();
  apiFormData.append('file', new Blob([buffer], { type: file.type }), file.name);
  apiFormData.append('document_type', documentType);

  const res = await fetch(`${API_BASE}/api/kyc/submit`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: apiFormData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { error?: string }).error ?? `Erreur ${res.status}`);
  }

  return res.json();
};

export const getAdminKYCList = async (
  statusFilter?: string,
): Promise<AdminKYCListResponse> => {
  const token = await getToken();
  const url = new URL(`${API_BASE}/api/kyc/admin/list`);
  if (statusFilter) url.searchParams.set('status', statusFilter);

  const res = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });

  if (!res.ok) throw new Error(`Erreur ${res.status}`);
  return res.json();
};

export const reviewKYCDocument = async (
  docId: string,
  decision: 'APPROVED' | 'COMPLEMENT_REQUESTED' | 'REJECTED',
  comment: string,
): Promise<KYCDocument> => {
  const token = await getToken();

  const res = await fetch(`${API_BASE}/api/kyc/review/${docId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ decision, comment }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { error?: string }).error ?? `Erreur ${res.status}`);
  }

  return res.json();
};
