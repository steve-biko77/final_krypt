import HeaderBox from '@/components/HeaderBox'
import KYCBanner from '@/components/KYCBanner'
import { getKYCStatus } from '@/lib/actions/kyc.actions'
import { getLoggedInUser } from '@/lib/actions/user.actions'

const Home = async () => {
  const [loggedIn, kycData] = await Promise.all([
    getLoggedInUser(),
    getKYCStatus(),
  ])

  return (
    <section className="home">
      <div className="home-content">
        <header className="home-header">
          <HeaderBox
            type="greeting"
            title="Bienvenue,"
            user={loggedIn?.firstName ?? 'Guest'}
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
