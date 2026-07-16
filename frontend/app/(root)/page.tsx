import Dashboard from '@/components/Dashboard'
import LandingPage from '@/components/LandingPage'
import { getKYCStatus } from '@/lib/actions/kyc.actions'
import { getMyTransfers } from '@/lib/actions/transfer.actions'
import { getLoggedInUser } from '@/lib/actions/user.actions'

// Refonte frontend (partie 2/4) — "/" sert désormais deux publics distincts :
// visiteur anonyme → landing page publique (LandingPage) ; utilisateur
// connecté → tableau de bord (Dashboard, refonte partie 3/4). Le gate
// d'authentification des AUTRES routes reste (root)/(protected)/layout.tsx.
const Home = async () => {
  const loggedIn = await getLoggedInUser()

  if (!loggedIn) {
    return <LandingPage />
  }

  const [kycData, myTransfers] = await Promise.all([
    getKYCStatus(),
    getMyTransfers(),
  ])

  return (
    <Dashboard
      firstName={loggedIn.firstName}
      isKycVerified={loggedIn.is_kyc_verified}
      kycStatus={kycData.status}
      transfers={myTransfers.results}
    />
  )
}

export default Home
