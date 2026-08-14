'use client'

import Image from 'next/image'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Menu } from 'lucide-react'
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { sidebarLinks } from '@/constants'
import { cn } from '@/lib/utils'
import UserMenu from '@/components/UserMenu'

/**
 * Correctif shadcn/ui — déjà basé sur Sheet (Radix) avant ce correctif, mais
 * jamais restylé (voir Sidebar.tsx pour le contexte complet). Même contenu
 * que la Sidebar desktop, dans un panneau coulissant.
 */
const MobileNav = ({ user, pendingAmlCount }: MobileNavProps) => {
  const pathname = usePathname()

  const visibleLinks = sidebarLinks.filter((item) => !item.adminOnly || user.is_staff)
  const mainLinks = visibleLinks.filter((item) => !item.adminOnly)
  const adminLinks = visibleLinks.filter((item) => item.adminOnly)

  // Correctif shadcn/ui — cible tactile mobile (min. 44px) : py-3 (contre
  // py-2.5 côté Sidebar desktop, non touchée) + gap-2 entre liens empilés
  // (au lieu de gap-1) pour un espacement suffisant au pouce. MobileNav ne
  // s'affiche jamais au-delà de md (cf. .root-layout, md:hidden), donc ces
  // valeurs n'ont pas besoin d'être conditionnées par un breakpoint : ce
  // composant EST déjà exclusivement mobile.
  const linkClassName = (isActive: boolean) =>
    cn(
      'flex items-center gap-3 rounded-lg px-3 py-3 min-h-11 transition-colors',
      isActive ? 'bg-blue-25 text-blue-700' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
    )

  return (
    <Sheet>
      <SheetTrigger className="flex items-center justify-center rounded-lg p-2.5 min-h-11 min-w-11 text-gray-600 hover:bg-gray-50">
        <Menu size={24} aria-hidden="true" />
        <span className="sr-only">Ouvrir le menu</span>
      </SheetTrigger>
      <SheetContent side="left" className="flex w-72 flex-col gap-6 border-none bg-white px-4 py-6">
        <Link href="/" className="flex items-center gap-2 px-2">
          <Image src="/icons/logo.svg" width={26} height={26} alt="Krypt logo" />
          <span className="font-ibm-plex-serif text-18 font-bold text-black-1">KRYPT</span>
        </Link>

        <div className="flex flex-1 flex-col justify-between overflow-y-auto">
          <div className="flex flex-col gap-6">
            <nav className="flex flex-col gap-2">
              {mainLinks.map((item) => {
                const isActive = pathname === item.route || pathname.startsWith(`${item.route}/`)
                const Icon = item.icon
                return (
                  <SheetClose asChild key={item.label}>
                    <Link href={item.route} className={linkClassName(isActive)}>
                      <Icon
                        size={20}
                        className={cn('shrink-0', isActive ? 'text-blue-600' : 'text-gray-400')}
                        aria-hidden="true"
                      />
                      <span className="text-14 font-semibold">{item.label}</span>
                    </Link>
                  </SheetClose>
                )
              })}
            </nav>

            {adminLinks.length > 0 && (
              <div className="flex flex-col gap-2 border-t border-gray-100 pt-4">
                <p className="px-3 pb-1 text-10 font-semibold uppercase tracking-wide text-gray-400">
                  Administration
                </p>
                {adminLinks.map((item) => {
                  // Cf. Sidebar.tsx — "/admin" ne doit s'allumer que sur sa
                  // propre page, pas sur /admin/kyc ou /admin/aml.
                  const isActive =
                    item.route === '/admin'
                      ? pathname === '/admin'
                      : pathname === item.route || pathname.startsWith(`${item.route}/`)
                  const Icon = item.icon
                  const badgeCount = item.badgeKey === 'amlPending' ? pendingAmlCount : undefined
                  return (
                    <SheetClose asChild key={item.label}>
                      <Link href={item.route} className={linkClassName(isActive)}>
                        <Icon
                          size={20}
                          className={cn('shrink-0', isActive ? 'text-blue-600' : 'text-gray-400')}
                          aria-hidden="true"
                        />
                        <span className="flex-1 text-14 font-semibold">{item.label}</span>
                        {!!badgeCount && <Badge variant="destructive">{badgeCount}</Badge>}
                      </Link>
                    </SheetClose>
                  )
                })}
              </div>
            )}
          </div>

          <UserMenu user={user} />
        </div>
      </SheetContent>
    </Sheet>
  )
}

export default MobileNav
