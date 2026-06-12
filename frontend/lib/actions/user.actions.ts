'use server';

import { cookies } from 'next/headers';
import { apiGet, apiPost } from '../api';

const TOKEN_COOKIE = 'krypt-access-token';

interface DjangoUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  is_kyc_verified: boolean;
  created_at: string | null;
}

interface AuthResponse {
  user: DjangoUser;
  tokens: { access: string; refresh: string };
}

function toUser(u: DjangoUser): User {
  return {
    id: u.id,
    $id: u.id,
    email: u.email,
    firstName: u.first_name,
    lastName: u.last_name,
    phone: u.phone,
    is_kyc_verified: u.is_kyc_verified,
    name: `${u.first_name} ${u.last_name}`,
    // legacy compat — keep so existing components don't crash
    userId: u.id,
    dwollaCustomerUrl: '',
    dwollaCustomerId: '',
    address1: '',
    city: '',
    state: '',
    postalCode: '',
    dateOfBirth: '',
    ssn: '',
  };
}

export const signIn = async ({ email, password }: { email: string; password: string }) => {
  const data = await apiPost<AuthResponse>('/api/auth/login', { email, password });

  const jar = await cookies();
  jar.set(TOKEN_COOKIE, data.tokens.access, {
    path: '/',
    httpOnly: true,
    sameSite: 'strict',
    secure: process.env.NODE_ENV === 'production',
    maxAge: 60 * 60,
  });

  return toUser(data.user);
};

export const signUp = async ({ email, password, firstName, lastName, phone }: SignUpParams) => {
  const data = await apiPost<AuthResponse>('/api/auth/register', {
    email,
    password,
    first_name: firstName,
    last_name: lastName,
    phone: phone ?? '',
  });

  const jar = await cookies();
  jar.set(TOKEN_COOKIE, data.tokens.access, {
    path: '/',
    httpOnly: true,
    sameSite: 'strict',
    secure: process.env.NODE_ENV === 'production',
    maxAge: 60 * 60,
  });

  return toUser(data.user);
};

export const getLoggedInUser = async (): Promise<User | null> => {
  try {
    const jar = await cookies();
    const token = jar.get(TOKEN_COOKIE)?.value;
    if (!token) return null;
    const data = await apiGet<{ user: DjangoUser }>('/api/auth/me', token);
    return toUser(data.user);
  } catch {
    return null;
  }
};

export const logoutAccount = async () => {
  const jar = await cookies();
  jar.delete(TOKEN_COOKIE);
  return true;
};
