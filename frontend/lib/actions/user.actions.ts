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
  is_2fa_enabled: boolean;
  is_staff: boolean;
  created_at: string | null;
}

interface AuthResponse {
  user: DjangoUser;
  tokens: { access: string; refresh: string };
}

interface TwoFARequiredResponse {
  requires_2fa: true;
  pre_auth_token: string;
}

export type SignInResult =
  | { requires_2fa: false; user: User }
  | { requires_2fa: true; pre_auth_token: string };

function toUser(u: DjangoUser): User {
  return {
    id: u.id,
    $id: u.id,
    email: u.email,
    firstName: u.first_name,
    lastName: u.last_name,
    phone: u.phone,
    is_kyc_verified: u.is_kyc_verified,
    is_2fa_enabled: u.is_2fa_enabled,
    is_staff: u.is_staff ?? false,
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

async function setAccessCookie(token: string) {
  const jar = await cookies();
  jar.set(TOKEN_COOKIE, token, {
    path: '/',
    httpOnly: true,
    // 'strict' bloque le cookie sur toute navigation top-level dont
    // l'origine n'est pas le site lui-même — y compris un clic sur un lien
    // depuis un client mail (le cas "Voir le récapitulatif") ou un favori,
    // même si une session valide existe déjà dans un autre onglet du MÊME
    // navigateur (le cookie est bien partagé entre onglets, ce n'est pas le
    // problème — cf. récap de la correction pour le diagnostic complet).
    // 'lax' envoie le cookie sur ces navigations GET top-level tout en
    // continuant de le bloquer sur les requêtes cross-site en sous-ressource
    // ou non-GET (formulaires, XHR/fetch) : protection CSRF inchangée pour
    // ce qui compte réellement.
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    maxAge: 60 * 60,
  });
}

export const signIn = async ({
  email,
  password,
}: {
  email: string;
  password: string;
}): Promise<SignInResult> => {
  const data = await apiPost<AuthResponse | TwoFARequiredResponse>(
    '/api/auth/login',
    { email, password },
  );

  if ('requires_2fa' in data && data.requires_2fa) {
    return { requires_2fa: true, pre_auth_token: data.pre_auth_token };
  }

  const authData = data as AuthResponse;
  await setAccessCookie(authData.tokens.access);
  return { requires_2fa: false, user: toUser(authData.user) };
};

export const completeTwoFactorSignIn = async ({
  pre_auth_token,
  totp_code,
}: {
  pre_auth_token: string;
  totp_code: string;
}): Promise<User> => {
  const data = await apiPost<AuthResponse>('/api/auth/2fa/login', {
    pre_auth_token,
    totp_code,
  });
  await setAccessCookie(data.tokens.access);
  return toUser(data.user);
};

export const signUp = async ({
  email,
  password,
  firstName,
  lastName,
  phone,
}: SignUpParams) => {
  const data = await apiPost<AuthResponse>('/api/auth/register', {
    email,
    password,
    first_name: firstName,
    last_name: lastName,
    phone: phone ?? '',
  });

  await setAccessCookie(data.tokens.access);
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
