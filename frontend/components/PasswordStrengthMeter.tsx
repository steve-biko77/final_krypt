'use client'

import { Check } from 'lucide-react'
import {
  evaluatePasswordStrength,
  PASSWORD_CRITERIA,
  STRENGTH_LABELS,
} from '@/lib/passwordStrength'

// Retour visuel seul : ce composant n'expose aucun callback de validation et
// n'est branché sur aucun resolver — il ne peut pas bloquer la soumission du
// formulaire. Les règles affichées reflètent celles réellement appliquées par
// POST /api/auth/register (voir l'en-tête de lib/passwordStrength.ts).

const SEGMENT_COLORS = ['bg-red-500', 'bg-orange-500', 'bg-success-600'] as const
const LABEL_COLORS = ['text-red-600', 'text-orange-600', 'text-success-700'] as const

export default function PasswordStrengthMeter({ password }: { password: string }) {
  const { met, level, filledSegments } = evaluatePasswordStrength(password)
  const label = level === 'empty' ? null : STRENGTH_LABELS[level]

  return (
    <div className="flex flex-col gap-2.5" data-testid="password-strength-meter">
      <div className="flex items-center gap-3">
        <div className="flex flex-1 gap-1.5" aria-hidden="true">
          {[0, 1, 2].map((index) => (
            <span
              key={index}
              className={`h-1.5 flex-1 rounded-full transition-colors ${
                index < filledSegments ? SEGMENT_COLORS[filledSegments - 1] : 'bg-gray-200'
              }`}
            />
          ))}
        </div>
        {/* aria-live : le lecteur d'écran annonce le changement de niveau sans
            que l'utilisateur ait à quitter le champ. */}
        <p
          aria-live="polite"
          className={`w-14 shrink-0 text-right text-12 font-semibold ${
            label ? LABEL_COLORS[filledSegments - 1] : 'text-transparent'
          }`}
        >
          {label ?? '—'}
        </p>
      </div>

      <ul className="flex flex-col gap-1">
        {PASSWORD_CRITERIA.map((criterion) => {
          const isMet = met[criterion.id]
          return (
            <li
              key={criterion.id}
              data-testid={`password-criterion-${criterion.id}`}
              data-met={isMet}
              className={`flex items-center gap-2 text-12 ${
                isMet ? 'text-success-700' : 'text-gray-500'
              }`}
            >
              <span
                aria-hidden="true"
                className={`flex size-4 shrink-0 items-center justify-center rounded-full ${
                  isMet ? 'bg-success-100 text-success-700' : 'bg-gray-200 text-transparent'
                }`}
              >
                <Check size={11} strokeWidth={3} />
              </span>
              <span>{criterion.label}</span>
              <span className="text-11 text-gray-500">
                {criterion.required ? '(requis)' : '(recommandé)'}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
