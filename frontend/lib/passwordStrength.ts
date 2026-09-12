// Indicateur de force du mot de passe — RETOUR VISUEL UNIQUEMENT.
//
// Règle réellement appliquée à l'inscription côté serveur :
//   backend/contexts/identity/adapters/api/serializers.py
//     RegisterSerializer.password = serializers.CharField(min_length=8, ...)
// C'est la seule contrainte que POST /api/auth/register fait respecter. Les
// AUTH_PASSWORD_VALIDATORS de backend/config/settings.py (MinimumLength,
// CommonPassword, NumericPassword) ne sont PAS appliqués sur ce chemin :
// django.contrib.auth.password_validation.validate_password n'y est jamais
// appelé (RegisterUserUseCase hache directement via DjangoAuthService), ils ne
// jouent que pour les formulaires Django (admin, createsuperuser).
//
// Les trois autres critères affichés (majuscule, chiffre, caractère spécial)
// sont donc présentés comme RECOMMANDÉS, pas comme requis : ils alimentent le
// score visuel sans être exigés par le serveur, et ne modifient aucune
// validation (zod côté client : authFormSchema, password: z.string().min(8)).

export type PasswordCriterionId = 'length' | 'uppercase' | 'digit' | 'special'

export interface PasswordCriterion {
  id: PasswordCriterionId
  label: string
  /** true = règle réellement refusée par le serveur si non respectée. */
  required: boolean
  isMet: (password: string) => boolean
}

export const PASSWORD_CRITERIA: readonly PasswordCriterion[] = [
  {
    id: 'length',
    label: 'Au moins 8 caractères',
    required: true,
    isMet: (password) => password.length >= 8,
  },
  {
    id: 'uppercase',
    label: 'Au moins 1 majuscule',
    required: false,
    isMet: (password) => /[A-Z]/.test(password),
  },
  {
    id: 'digit',
    label: 'Au moins 1 chiffre',
    required: false,
    isMet: (password) => /[0-9]/.test(password),
  },
  {
    id: 'special',
    label: 'Au moins 1 caractère spécial',
    required: false,
    isMet: (password) => /[^A-Za-z0-9]/.test(password),
  },
] as const

export type PasswordStrengthLevel = 'empty' | 'weak' | 'medium' | 'strong'

export interface PasswordStrength {
  /** Critères remplis, dans l'ordre de PASSWORD_CRITERIA. */
  met: Record<PasswordCriterionId, boolean>
  /** Nombre de critères remplis (0 à 4). */
  metCount: number
  /** Niveau affiché : 0, 1, 2 ou 3 segments remplis. */
  level: PasswordStrengthLevel
  /** Segments remplis sur la barre (0 à 3), dérivé de `level`. */
  filledSegments: number
}

const SEGMENTS_BY_LEVEL: Record<PasswordStrengthLevel, number> = {
  empty: 0,
  weak: 1,
  medium: 2,
  strong: 3,
}

export function evaluatePasswordStrength(password: string): PasswordStrength {
  const met = PASSWORD_CRITERIA.reduce(
    (acc, criterion) => {
      acc[criterion.id] = criterion.isMet(password)
      return acc
    },
    {} as Record<PasswordCriterionId, boolean>
  )

  const metCount = PASSWORD_CRITERIA.filter((criterion) => met[criterion.id]).length

  let level: PasswordStrengthLevel
  if (password.length === 0) {
    // Tant que rien n'est saisi, la barre reste vide (pas de "faible" rouge
    // affiché d'emblée sur un champ intact).
    level = 'empty'
  } else if (!met.length) {
    // Le seul critère refusé par le serveur n'est pas atteint : jamais plus
    // d'un segment, quel que soit le reste.
    level = 'weak'
  } else if (metCount === 4) {
    level = 'strong'
  } else if (metCount === 3) {
    level = 'medium'
  } else {
    level = 'weak'
  }

  return { met, metCount, level, filledSegments: SEGMENTS_BY_LEVEL[level] }
}

export const STRENGTH_LABELS: Record<Exclude<PasswordStrengthLevel, 'empty'>, string> = {
  weak: 'Faible',
  medium: 'Moyen',
  strong: 'Fort',
}
