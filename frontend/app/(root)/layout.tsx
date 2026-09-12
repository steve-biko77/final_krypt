import BottomNav from '@/components/BottomNav'
import MobileNav from '@/components/MobileNav'
import Sidebar from '@/components/Sidebar'
import { getLoggedInUser } from '@/lib/actions/user.actions'
import { getAdminAMLPending } from '@/lib/actions/admin-aml.actions'
import Image from 'next/image'

// Refonte frontend (partie 2/4) — "/" doit devenir une landing page publique
// (accessible sans connexion) : ce layout ne redirige donc plus jamais. La
// protection des autres routes (transfer, kyc, admin, etc.) est assurée par
// (root)/(protected)/layout.tsx, inchangée. Le chrome connecté (Sidebar,
// MobileNav) n'est rendu que si l'utilisateur est connecté ; un visiteur
// anonyme voit ses children (page d'accueil publique) en plein écran, sans
// cette navigation qui suppose un `user` non nul.
export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const loggedIn = await getLoggedInUser()

  if (!loggedIn) {
    return <main className="min-h-screen w-full font-inter">{children}</main>
  }

  // Correctif shadcn/ui — badge numérique de dossiers AML en attente sur le
  // lien Console AML. /api/admin/aml/pending exige is_staff ET 2FA activée
  // (IsStaffWith2FA) : un admin sans 2FA obtiendrait un 403 ici — échec
  // silencieux (pas de badge) plutôt que de casser toute la navigation.
  let pendingAmlCount: number | undefined
  if (loggedIn.is_staff) {
    try {
      const pending = await getAdminAMLPending()
      pendingAmlCount = pending.count
    } catch {
      pendingAmlCount = undefined
    }
  }

  return (
    <main className='flex h-screen w-full font-inter'>
      <Sidebar user={loggedIn} pendingAmlCount={pendingAmlCount} />
      <div className='flex size-full flex-col'>
        <div className='root-layout'>
          <Image src='/icons/logo.svg' width={30} height={30} alt='logo' />
          <div>
            <MobileNav user={loggedIn} pendingAmlCount={pendingAmlCount} />
          </div>
        </div>
        {/* Optimisation mobile-first — espace réservé pour que la BottomNav
            fixe (voir plus bas) ne masque jamais le bas du contenu ; nul à
            partir de md, où la BottomNav ne s'affiche plus (md:hidden). */}
        <div className='pb-[calc(3.5rem+env(safe-area-inset-bottom))] md:pb-0'>
          {children}
        </div>
      </div>
      <BottomNav />
    </main>
  )
}
