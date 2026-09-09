import { describe, expect, it } from 'vitest'
import { readFileSync } from 'fs'
import { join } from 'path'

// Correctif Framer Motion — vérifie que les 3 emplacements d'animation
// ciblés appellent explicitement useReducedMotion (framer-motion) et
// branchent leur comportement dessus, plutôt que de supposer que l'usage de
// "motion"/"AnimatePresence" respecte prefers-reduced-motion implicitement.
// Une vérification DOM par timing (waitFor vs assertion synchrone) s'est
// avérée peu fiable : framer-motion différe ses écritures DOM via son propre
// ordonnanceur même pour un useMotionValue.set() "instantané", donc pas un
// signal de test exploitable — la vérification statique du branchement
// explicite est le signal robuste ici.
const ROOT = join(__dirname, '..')

const TARGETS = [
  {
    label: 'AmountConversionDisplay (comptage du montant FCFA)',
    file: join(ROOT, 'components/AmountConversionDisplay.tsx'),
  },
  {
    label: 'RecentTransfersList (apparition en cascade des JourneyCard)',
    file: join(ROOT, 'components/RecentTransfersList.tsx'),
  },
  {
    label: 'TransferStepper (transition entre les 3 étapes du tunnel)',
    file: join(ROOT, 'app/(root)/(protected)/transfer/TransferStepper.tsx'),
  },
  {
    label: "SignUpSuccessOverlay (confettis après création de compte)",
    file: join(ROOT, 'components/SignUpSuccessOverlay.tsx'),
  },
]

describe('prefers-reduced-motion respecté explicitement (framer-motion)', () => {
  for (const { label, file } of TARGETS) {
    it(`${label} importe et utilise useReducedMotion`, () => {
      const content = readFileSync(file, 'utf-8')
      expect(content).toMatch(/useReducedMotion/)
      // Doit être appelé (pas seulement importé sans être utilisé).
      expect(content).toMatch(/useReducedMotion\(\)/)
      // Le résultat doit conditionner le comportement (prefersReducedMotion
      // référencé au moins une fois en dehors de sa propre déclaration).
      const occurrences = content.match(/prefersReducedMotion/g) ?? []
      expect(occurrences.length).toBeGreaterThan(1)
    })
  }
})
