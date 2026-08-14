'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { sidebarLinks } from '@/constants'
import { cn } from '@/lib/utils'

// Optimisation mobile-first — 4 destinations principales de l'espace
// utilisateur, atteignables au pouce. Sous-ensemble volontaire de
// sidebarLinks (mêmes routes/icônes/labels que la Sidebar desktop, jamais
// dupliqués) : pas de "Vérification KYC" ni de liens admin ici, cf. demande.
const BOTTOM_NAV_ROUTES = ['/', '/transfer', '/transaction-history', '/security']

/**
 * Barre de navigation basse fixe — visible uniquement sous md (md:hidden) :
 * la Sidebar desktop (max-md:hidden) et la MobileNav (Sheet, md:hidden)
 * existantes restent inchangées et continuent de fonctionner exactement
 * comme avant. gère env(safe-area-inset-bottom) pour les téléphones à
 * encoche (barre d'accueil iOS).
 */
const BottomNav = () => {
  const pathname = usePathname()
  const links = sidebarLinks.filter((item) => BOTTOM_NAV_ROUTES.includes(item.route))

  return (
    <nav
      aria-label="Navigation principale"
      data-testid="bottom-nav"
      className="fixed inset-x-0 bottom-0 z-40 flex border-t border-gray-200 bg-white pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {links.map((item) => {
        const isActive =
          item.route === '/' ? pathname === '/' : pathname === item.route || pathname.startsWith(`${item.route}/`)
        const Icon = item.icon
        return (
          <Link
            key={item.label}
            href={item.route}
            aria-current={isActive ? 'page' : undefined}
            className={cn(
              'flex min-h-11 flex-1 flex-col items-center justify-center gap-0.5 py-2 text-11 font-medium transition-colors',
              isActive ? 'text-blue-600' : 'text-gray-500'
            )}
          >
            <Icon
              size={22}
              className={cn('shrink-0', isActive ? 'text-blue-600' : 'text-gray-400')}
              aria-hidden="true"
            />
            <span className="truncate">{item.shortLabel ?? item.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}

export default BottomNav
