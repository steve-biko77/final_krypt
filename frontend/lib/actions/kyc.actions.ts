'use server';

import { cookies } from 'next/headers';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type KYCDocumentStatus = 'PENDING' | 'APPROVED' | 'REJECTED';

export interface KYCDocument {
  id: string;
  document_type: string;
  status: KYCDocumentStatus;
  file_path: string;
  submitted_at: string | null;
  reviewed_at: string | null;
}

export interface KYCStatusResponse {
  status: KYCDocumentStatus | null;
  document: KYCDocument | null;
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
  apiFormData.append(
    'file',
    new Blob([buffer], { type: file.type }),
    file.name,
  );
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
