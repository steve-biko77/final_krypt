import MobileNav from '@/components/MobileNav'
import Sidebar from '@/components/Sidebar'
import { getLoggedInUser } from '@/lib/actions/user.actions'
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

  return (
    <main className='flex h-screen w-full font-inter'>
      <Sidebar user={loggedIn} />
      <div className='flex size-full flex-col'>
        <div className='root-layout'>
          <Image src='/icons/logo.svg' width={30} height={30} alt='logo' />
          <div>
            <MobileNav user={loggedIn} />
          </div>
        </div>
        {children}
      </div>
    </main>
  )
}
