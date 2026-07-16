import Dashboard from '@/components/Dashboard'
import LandingPage from '@/components/LandingPage'
import { getKYCStatus } from '@/lib/actions/kyc.actions'
import { getLoggedInUser } from '@/lib/actions/user.actions'

// Refonte frontend (partie 2/4) — "/" sert désormais deux publics distincts :
// visiteur anonyme → landing page publique (LandingPage) ; utilisateur
// connecté → tableau de bord (Dashboard, refonte partie 3/4). Le gate
// d'authentification des AUTRES routes reste (root)/(protected)/layout.tsx.
//
// Correctif Skeleton — les transferts récents sont désormais chargés côté
// client par RecentTransfersList (son propre useEffect), pas ici : ça donne
// un état de chargement réellement visible (un rendu SSR déjà résolu n'en
// montre jamais un) et reste testable simplement (mock de l'action).
const Home = async () => {
  const loggedIn = await getLoggedInUser()

  if (!loggedIn) {
    return <LandingPage />
  }

  const kycData = await getKYCStatus()

  return (
    <Dashboard
      firstName={loggedIn.firstName}
      isKycVerified={loggedIn.is_kyc_verified}
      kycStatus={kycData.status}
    />
  )
}

export default Home
