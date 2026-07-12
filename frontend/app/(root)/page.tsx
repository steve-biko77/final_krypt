import HeaderBox from '@/components/HeaderBox'
import KYCBanner from '@/components/KYCBanner'
import LandingPage from '@/components/LandingPage'
import { getKYCStatus } from '@/lib/actions/kyc.actions'
import { getLoggedInUser } from '@/lib/actions/user.actions'

// Refonte frontend (partie 2/4) — "/" sert désormais deux publics distincts :
// visiteur anonyme → landing page publique (LandingPage) ; utilisateur
// connecté → tableau de bord existant, inchangé. Le gate d'authentification
// des AUTRES routes reste (root)/(protected)/layout.tsx.
const Home = async () => {
  const loggedIn = await getLoggedInUser()

  if (!loggedIn) {
    return <LandingPage />
  }

  const kycData = await getKYCStatus()

  return (
    <section className="home">
      <div className="home-content">
        <header className="home-header">
          <HeaderBox
            type="greeting"
            title="Bienvenue,"
            user={loggedIn.firstName}
            subtext="Gérez vos transferts France → Cameroun via Mobile Money"
          />
        </header>

        <div className="p-6">
          <KYCBanner kycStatus={kycData.status} />

          <div className="flex flex-col gap-4 text-gray-600">
            <p className="text-16">
              Les transferts MTN MoMo / Orange Money seront disponibles après validation de votre identité.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

export default Home
