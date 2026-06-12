import HeaderBox from '@/components/HeaderBox'
import { getLoggedInUser } from '@/lib/actions/user.actions'

const Home = async () => {
  const loggedIn = await getLoggedInUser()

  return (
    <section className='home'>
      <div className='home-content'>
        <header className='home-header'>
          <HeaderBox
            type='greeting'
            title='Bienvenue,'
            user={loggedIn?.firstName ?? 'Guest'}
            subtext='Gérez vos transferts France → Cameroun via Mobile Money'
          />
        </header>

        <div className='flex flex-col gap-4 p-6 text-gray-600'>
          <p className='text-16'>
            Les transferts MTN MoMo / Orange Money seront bientôt disponibles.
          </p>
        </div>
      </div>
    </section>
  )
}

export default Home
