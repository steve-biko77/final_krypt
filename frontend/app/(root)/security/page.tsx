import HeaderBox from '@/components/HeaderBox'
import TwoFactorManager from '@/components/TwoFactorManager'
import { getLoggedInUser } from '@/lib/actions/user.actions'

const SecurityPage = async () => {
  const user = await getLoggedInUser()

  return (
    <section className="flex flex-col gap-8 p-8 max-w-2xl">
      <HeaderBox
        title="Sécurité du compte"
        subtext="Gérez l'authentification à deux facteurs (2FA)"
      />
      <TwoFactorManager is2faEnabled={user?.is_2fa_enabled ?? false} />
    </section>
  )
}

export default SecurityPage
