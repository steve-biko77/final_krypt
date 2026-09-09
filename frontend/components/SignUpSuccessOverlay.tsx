'use client'

import Image from 'next/image'
import { useCallback, useEffect, useRef } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

// Écran de bienvenue affiché après une inscription RÉUSSIE, juste avant la
// redirection vers le tableau de bord. Purement cosmétique : le compte est
// déjà créé et la session posée à ce stade (AuthForm appelle signUp() avant
// de monter ce composant) ; ici on ne fait que différer le router.push.
//
// Confettis en Framer Motion (déjà utilisé ailleurs : TransferTimeline,
// RecentTransfersList, TransferStepper) plutôt qu'une librairie de plus.

const AUTO_CONTINUE_DELAY_MS = 2600

const CONFETTI_COLORS = ['#1570EF', '#039855', '#EE46BC', '#F79009', '#6172F3'] as const

// Trajectoires déterministes (pas de Math.random) : rendu stable entre le
// serveur et le client, et test reproductible.
const CONFETTI = Array.from({ length: 28 }, (_, index) => ({
  id: index,
  left: `${(index * 37) % 100}%`,
  color: CONFETTI_COLORS[index % CONFETTI_COLORS.length],
  delay: (index % 7) * 0.09,
  duration: 1.9 + ((index % 5) * 0.18),
  drift: ((index % 5) - 2) * 24,
  spin: index % 2 === 0 ? 420 : -380,
  size: 6 + (index % 3) * 3,
}))

export default function SignUpSuccessOverlay({ onContinue }: { onContinue: () => void }) {
  const prefersReducedMotion = useReducedMotion()
  // Le bouton "Continuer" et le délai automatique visent la même action :
  // on garantit qu'elle ne part qu'une fois (pas de double router.push).
  const hasContinuedRef = useRef(false)

  const handleContinue = useCallback(() => {
    if (hasContinuedRef.current) return
    hasContinuedRef.current = true
    onContinue()
  }, [onContinue])

  useEffect(() => {
    const timer = setTimeout(handleContinue, AUTO_CONTINUE_DELAY_MS)
    return () => clearTimeout(timer)
  }, [handleContinue])

  return (
    <div
      data-testid="signup-success-overlay"
      className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 overflow-hidden bg-white px-6"
    >
      {/* prefers-reduced-motion : aucun confetti, le message s'affiche
          directement (pas d'animation d'entrée non plus). */}
      {!prefersReducedMotion && (
        <div className="pointer-events-none absolute inset-0" aria-hidden="true">
          {CONFETTI.map((piece) => (
            <motion.span
              key={piece.id}
              className="absolute top-0 block rounded-[2px]"
              style={{
                left: piece.left,
                width: piece.size,
                height: piece.size * 2,
                backgroundColor: piece.color,
              }}
              initial={{ y: '-10vh', x: 0, rotate: 0, opacity: 0 }}
              animate={{
                y: '110vh',
                x: piece.drift,
                rotate: piece.spin,
                opacity: [0, 1, 1, 0],
              }}
              transition={{ duration: piece.duration, delay: piece.delay, ease: 'easeIn' }}
            />
          ))}
        </div>
      )}

      <motion.div
        className="relative flex max-w-sm flex-col items-center gap-4 text-center"
        initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.94, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
      >
        <div className="flex items-center gap-1.5">
          <Image src="/icons/logo.svg" width={30} height={30} alt="" />
          <span className="text-20 font-ibm-plex-serif font-bold text-black-1">Krypt</span>
        </div>

        <CheckCircle2 size={52} className="text-success-600" aria-hidden="true" />

        <h1 className="font-heading tracking-heading text-30 font-extrabold text-gray-900">
          Bienvenue sur KRYPT
        </h1>
        <p className="text-16 text-gray-600">
          Votre compte est créé. Vous pouvez dès maintenant simuler et suivre vos transferts
          vers le Cameroun, en toute transparence.
        </p>

        <Button variant="brand" size="lg" className="mt-2 w-full" onClick={handleContinue}>
          Continuer
        </Button>
      </motion.div>
    </div>
  )
}
