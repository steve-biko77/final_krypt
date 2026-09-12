'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useCallback, useRef, useState } from 'react'
import { useReducedMotion } from 'framer-motion'
import { Button } from '@/components/ui/button'

// Carrousel d'introduction — habillage de démonstration, mobile uniquement
// (< md, cf. le `md:hidden` posé par LandingPage). Aucune logique métier :
// les deux seules actions sont les liens /sign-up et /sign-in déjà présents
// dans l'en-tête de la landing (masquée sous md pendant que ce carrousel
// occupe le premier écran). Sur desktop le composant n'est jamais visible et
// la landing existante est rendue telle quelle.
//
// Le défilement tactile est délégué au navigateur (overflow-x + scroll-snap)
// plutôt qu'à une gestion de gestes maison : swipe natif, inertie et
// accessibilité clavier gratuits, aucune dépendance ajoutée.

// Hauteur de la bande image, partagée entre l'image et la position des points
// de pagination (qui sont posés hors du conteneur défilant pour rester fixes
// d'une slide à l'autre) — une seule source de vérité pour éviter la dérive.
const IMAGE_BAND_HEIGHT = '46dvh'

const SLIDES = [
  {
    image: '/krypt_demo/envoi.jpg',
    alt: "Deux femmes consultent l'application KRYPT sur un téléphone",
    title: "Envoyez de l'argent, en toute transparence",
    description: 'Frais et taux affichés avant tout engagement, sans surprise à l’arrivée.',
  },
  {
    image: '/krypt_demo/portrait.jpg',
    alt: 'Portrait souriant d’un utilisateur de KRYPT',
    title: 'Suivez chaque transfert, en toute confiance',
    description: 'Chaque étape est tracée et vérifiable sur la blockchain Polygon.',
  },
  {
    image: '/krypt_demo/duo.jpg',
    alt: 'Un homme et sa mère consultent la confirmation d’un transfert',
    title: 'Restez proche de ceux qui comptent',
    description: 'De la France vers le Cameroun, sur MTN MoMo ou Orange Money.',
  },
] as const

export default function MobileOnboardingCarousel() {
  const prefersReducedMotion = useReducedMotion()
  const scrollerRef = useRef<HTMLDivElement>(null)
  const [activeIndex, setActiveIndex] = useState(0)

  const handleScroll = useCallback(() => {
    const scroller = scrollerRef.current
    if (!scroller || scroller.clientWidth === 0) return
    const index = Math.round(scroller.scrollLeft / scroller.clientWidth)
    setActiveIndex(Math.min(Math.max(index, 0), SLIDES.length - 1))
  }, [])

  const goToSlide = useCallback(
    (index: number) => {
      const scroller = scrollerRef.current
      if (!scroller) return
      scroller.scrollTo({
        left: index * scroller.clientWidth,
        behavior: prefersReducedMotion ? 'auto' : 'smooth',
      })
      // jsdom (et un navigateur en scroll-behavior instantané) n'émet pas
      // toujours l'événement scroll : on reflète l'intention tout de suite.
      setActiveIndex(index)
    },
    [prefersReducedMotion]
  )

  return (
    <section
      aria-label="Découvrir KRYPT"
      data-testid="mobile-onboarding-carousel"
      className="flex h-[100dvh] flex-col bg-white"
    >
      <div className="flex shrink-0 items-center gap-1.5 px-5 py-4">
        <Image src="/icons/logo.svg" width={28} height={28} alt="Krypt logo" />
        <span className="text-20 font-ibm-plex-serif font-bold text-black-1">Krypt</span>
      </div>

      <div className="relative min-h-0 flex-1">
        <div
          ref={scrollerRef}
          onScroll={handleScroll}
          className="no-scrollbar flex h-full snap-x snap-mandatory overflow-x-auto overflow-y-hidden"
        >
          {SLIDES.map((slide, index) => (
            <article
              key={slide.title}
              className="flex h-full w-full shrink-0 snap-center snap-always flex-col"
            >
              {/* bg-black-1 : fond de repli si l'image ne charge pas (démo) */}
              <div
                className="relative w-full shrink-0 overflow-hidden rounded-b-3xl bg-black-1"
                style={{ height: IMAGE_BAND_HEIGHT }}
              >
                <Image
                  src={slide.image}
                  alt={slide.alt}
                  fill
                  sizes="100vw"
                  priority={index === 0}
                  className="object-cover"
                />
              </div>
              <div className="flex flex-col gap-2 px-6 pt-8">
                <h2 className="font-heading tracking-heading text-24 font-extrabold text-gray-900">
                  {slide.title}
                </h2>
                <p className="text-14 text-gray-600">{slide.description}</p>
              </div>
            </article>
          ))}
        </div>

        {/* Points de pagination : posés au bas de la bande image, hors du
            conteneur défilant pour ne pas glisser avec les slides. */}
        <div
          className="pointer-events-none absolute inset-x-0 flex -translate-y-6 justify-center"
          style={{ top: IMAGE_BAND_HEIGHT }}
        >
          <div className="pointer-events-auto flex items-center gap-2 rounded-full bg-black-1/40 px-3 py-2 backdrop-blur-sm">
            {SLIDES.map((slide, index) => {
              const isActive = index === activeIndex
              return (
                <button
                  key={slide.title}
                  type="button"
                  onClick={() => goToSlide(index)}
                  aria-label={`Aller à l'écran ${index + 1} sur ${SLIDES.length}`}
                  aria-current={isActive ? 'true' : undefined}
                  className="flex size-6 items-center justify-center"
                >
                  <span
                    aria-hidden="true"
                    className={
                      isActive
                        ? 'h-2 w-6 rounded-full bg-white transition-all'
                        : 'size-2 rounded-full bg-white/50 transition-all'
                    }
                  />
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Actions fixes : même position sur les 3 slides (hors du conteneur
          défilant), au bas de l'écran. */}
      <div className="flex shrink-0 flex-col gap-3 px-6 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-4">
        <Button asChild variant="brand" size="lg" className="w-full">
          <Link href="/sign-up">Créer un compte</Link>
        </Button>
        <Button asChild variant="outline" size="lg" className="w-full">
          <Link href="/sign-in">Connexion</Link>
        </Button>
      </div>
    </section>
  )
}
