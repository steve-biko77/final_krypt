'use client'

import Image from 'next/image'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { sidebarLinks } from '@/constants'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import UserMenu from '@/components/UserMenu'

/**
 * Correctif shadcn/ui — navigation principale jamais retouchée visuellement
 * depuis les premiers sprints (seule sa condition d'affichage a changé en
 * partie 1/4). Logique de routes/permissions (is_staff) inchangée ; seul le
 * visuel/l'interaction sont refaits. Palette : uniquement les tokens déjà
 * établis (blue-25/600/700 pour l'état actif — mêmes tokens que l'avatar
 * JourneyCard ; success/red déjà utilisés ailleurs), aucune nouvelle couleur.
 */
const Sidebar = ({ user, pendingAmlCount }: SiderbarProps) => {
  const pathname = usePathname()

  const visibleLinks = sidebarLinks.filter((item) => !item.adminOnly || user.is_staff)
  const mainLinks = visibleLinks.filter((item) => !item.adminOnly)
  const adminLinks = visibleLinks.filter((item) => item.adminOnly)

  const linkClassName = (isActive: boolean) =>
    cn(
      'flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors',
      isActive ? 'bg-blue-25 text-blue-700' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
    )

  return (
    <section className="sticky left-0 top-0 flex h-screen w-64 shrink-0 flex-col justify-between border-r border-gray-200 bg-white px-3 py-6 max-md:hidden">
      <div className="flex flex-col gap-6">
        {/* Logo compact — icône + nom, pas un grand bandeau */}
        <Link href="/" className="flex items-center gap-2 px-2">
          <Image src="/icons/logo.svg" width={26} height={26} alt="Krypt logo" />
          <span className="font-ibm-plex-serif text-18 font-bold text-black-1">KRYPT</span>
        </Link>

        <nav className="flex flex-col gap-1">
          {mainLinks.map((item) => {
            const isActive = pathname === item.route || pathname.startsWith(`${item.route}/`)
            const Icon = item.icon
            return (
              <Link href={item.route} key={item.label} className={linkClassName(isActive)}>
                <Icon
                  size={20}
                  className={cn('shrink-0', isActive ? 'text-blue-600' : 'text-gray-400')}
                  aria-hidden="true"
                />
                <span className="text-14 font-semibold">{item.label}</span>
              </Link>
            )
          })}
        </nav>

        {adminLinks.length > 0 && (
          <div className="flex flex-col gap-1 border-t border-gray-100 pt-4">
            <p className="px-3 pb-1 text-10 font-semibold uppercase tracking-wide text-gray-400">
              Administration
            </p>
            {adminLinks.map((item) => {
              // "/admin" (Vue d'ensemble) ne doit s'illuminer que sur sa
              // propre page — un startsWith générique la ferait aussi
              // matcher /admin/kyc et /admin/aml, allumant deux liens à la
              // fois.
              const isActive =
                item.route === '/admin'
                  ? pathname === '/admin'
                  : pathname === item.route || pathname.startsWith(`${item.route}/`)
              const Icon = item.icon
              const badgeCount = item.badgeKey === 'amlPending' ? pendingAmlCount : undefined
              return (
                <Link href={item.route} key={item.label} className={linkClassName(isActive)}>
                  <Icon
                    size={20}
                    className={cn('shrink-0', isActive ? 'text-blue-600' : 'text-gray-400')}
                    aria-hidden="true"
                  />
                  <span className="flex-1 text-14 font-semibold">{item.label}</span>
                  {!!badgeCount && <Badge variant="destructive">{badgeCount}</Badge>}
                </Link>
              )
            })}
          </div>
        )}
      </div>

      <UserMenu user={user} />
    </section>
  )
}

export default Sidebar
