import { redirect } from 'next/navigation'
import { getLoggedInUser } from '@/lib/actions/user.actions'

// Refonte frontend (partie 2/4) — gate d'authentification déplacé ici depuis
// (root)/layout.tsx pour permettre à "/" de devenir une landing page publique
// (partie 2/4) sans affaiblir la protection des routes existantes : ce groupe
// de routes (admin, kyc, my-banks, payment-transfer, security,
// transaction-history, transfer) garde EXACTEMENT le même comportement
// qu'avant (redirect immédiat si non connecté) — seules les URLs restent
// inchangées, un groupe de routes entre parenthèses n'apparaît jamais dans le
// chemin.
export default async function ProtectedLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const loggedIn = await getLoggedInUser()

  if (!loggedIn) redirect('/sign-in')

  return <>{children}</>
}
