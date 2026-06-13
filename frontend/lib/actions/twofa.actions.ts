'use server';

import { cookies } from 'next/headers';
import { apiPost } from '../api';

async function getToken(): Promise<string> {
  const token = (await cookies()).get('krypt-access-token')?.value;
  if (!token) throw new Error('Not authenticated');
  return token;
}

export interface TwoFASetupData {
  secret: string;
  qr_uri: string;
  qr_image: string;
}

export const setup2FA = async (): Promise<TwoFASetupData> => {
  const token = await getToken();
  return apiPost<TwoFASetupData>('/api/auth/2fa/setup', {}, token);
};

export const verify2FA = async (
  totp_code: string,
): Promise<{ recovery_codes: string[] }> => {
  const token = await getToken();
  return apiPost('/api/auth/2fa/verify', { totp_code }, token);
};

export const disable2FA = async (totp_code: string): Promise<void> => {
  const token = await getToken();
  await apiPost('/api/auth/2fa/disable', { totp_code }, token);
};
