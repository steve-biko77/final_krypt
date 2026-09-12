"use client"

import {
  CircleCheckIcon,
  InfoIcon,
  Loader2Icon,
  OctagonXIcon,
  TriangleAlertIcon,
} from "lucide-react"
import { Toaster as Sonner, type ToasterProps } from "sonner"

// Projet en mode clair uniquement (pas de dark mode) — pas de next-themes ici,
// theme figé plutôt que dépendant d'une préférence système jamais appliquée
// ailleurs dans l'app.
//
// Correctif toast superposé au contenu — position="top-right" (standard
// desktop, coin fixe, ne chevauche jamais un titre de page centré/pleine
// largeur comme "Envoyer de l'argent"). Sonner bascule lui-même en pleine
// largeur centrée sous 600px (cf. node_modules/sonner/dist/styles.css,
// @media max-width:600px) : la même position="top-right" devient donc
// automatiquement "top-center" sur mobile, sans logique supplémentaire. Les
// deux offsets ci-dessous ajoutent juste la marge de sécurité par plateforme :
// - offset (desktop) : coin haut-droit, à distance du bord.
// - mobileOffset (<600px) : sous le header mobile (.root-layout, h-16) pour
//   ne jamais le chevaucher ; la BottomNav ajoutée n'est pas concernée, un
//   toast en haut d'écran ne peut pas la recouvrir.
const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="light"
      position="top-right"
      offset={{ top: 20, right: 20 }}
      mobileOffset={{ top: 'calc(4rem + env(safe-area-inset-top) + 0.75rem)' }}
      className="toaster group"
      icons={{
        success: <CircleCheckIcon className="size-4" />,
        info: <InfoIcon className="size-4" />,
        warning: <TriangleAlertIcon className="size-4" />,
        error: <OctagonXIcon className="size-4" />,
        loading: <Loader2Icon className="size-4 animate-spin" />,
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
