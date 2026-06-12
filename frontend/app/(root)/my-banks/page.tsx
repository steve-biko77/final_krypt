import HeaderBox from '@/components/HeaderBox'
import { getLoggedInUser } from '@/lib/actions/user.actions'

const MyBanks = async () => {
  const loggedIn = await getLoggedInUser()

  return (
    <section className='flex'>
      <div className='my-banks'>
        <HeaderBox
          title='Mes comptes'
          subtext={`Connecté en tant que ${loggedIn?.firstName ?? ''}`}
        />
        <div className='space-y-4 p-6'>
          <p className='text-16 text-gray-600'>
            La connexion aux comptes Mobile Money sera disponible prochainement.
          </p>
        </div>
      </div>
    </section>
  )
}

export default MyBanks
