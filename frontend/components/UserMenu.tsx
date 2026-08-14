'use client'

import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ChevronDown, LogOut, ShieldCheck } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { logoutAccount } from '@/lib/actions/user.actions'

function initials(firstName: string, lastName: string): string {
  const first = firstName?.[0] ?? ''
  const last = lastName?.[0] ?? ''
  return (first + last).toUpperCase() || '?'
}

/**
 * Correctif shadcn/ui — bloc compte utilisateur (bas de la Sidebar / du
 * MobileNav) : avatar (initiales) + nom + chevron déclenchant un vrai
 * DropdownMenu Radix, remplace Footer.tsx (classes CSS cassées, menu "fait
 * maison" inexistant — le logout n'était qu'une icône cliquable directe).
 */
export default function UserMenu({ user }: UserMenuProps) {
  const router = useRouter()

  const handleLogout = async () => {
    await logoutAccount()
    router.push('/sign-in')
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full items-center gap-2.5 rounded-lg p-2 text-left transition-colors hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
        <Avatar>
          <AvatarFallback className="bg-blue-25 font-heading font-bold text-blue-700">
            {initials(user.firstName, user.lastName)}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1 max-xl:hidden">
          <p className="truncate text-14 font-semibold text-gray-900">{user.firstName}</p>
          <p className="truncate text-12 text-gray-500">{user.email}</p>
        </div>
        <ChevronDown size={16} className="shrink-0 text-gray-400 max-xl:hidden" aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" side="top" className="w-56">
        {/* max-md: cible tactile 44px sur mobile (Sheet MobileNav) ; ce menu
            est partagé avec la Sidebar desktop (souris), donc inchangé à
            partir de md. */}
        <DropdownMenuItem asChild className="max-md:min-h-11">
          <Link href="/security" className="cursor-pointer">
            <ShieldCheck size={16} aria-hidden="true" />
            Sécurité
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={handleLogout}
          className="cursor-pointer text-red-600 focus:text-red-600 max-md:min-h-11"
        >
          <LogOut size={16} aria-hidden="true" />
          Se déconnecter
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
