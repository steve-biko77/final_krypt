import TwoFactorManager from '@/components/TwoFactorManager'
import { getLoggedInUser } from '@/lib/actions/user.actions'

const SecurityPage = async () => {
  const user = await getLoggedInUser()

  return (
    <section className="flex flex-col gap-8 p-4 sm:p-8 max-w-2xl">
      <div>
        <h1 className="font-heading tracking-heading text-24 sm:text-30 font-bold text-gray-900">
          Sécurité du compte
        </h1>
        <p className="text-14 text-gray-500 mt-1">
          Gérez l&apos;authentification à deux facteurs (2FA)
        </p>
      </div>
      <div className="rounded-2xl border border-gray-200 shadow-form p-5 sm:p-6">
        <TwoFactorManager is2faEnabled={user?.is_2fa_enabled ?? false} />
      </div>
    </section>
  )
}

export default SecurityPage
