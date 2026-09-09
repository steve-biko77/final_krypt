import { describe, expect, it } from 'vitest'
import {
  evaluatePasswordStrength,
  PASSWORD_CRITERIA,
} from './passwordStrength'

describe('passwordStrength — critères affichés', () => {
  it("ne marque comme REQUIS que la règle réellement appliquée par le serveur (min 8 caractères)", () => {
    // RegisterSerializer.password = CharField(min_length=8) est la seule
    // contrainte de POST /api/auth/register ; les 3 autres critères sont
    // affichés en tant que recommandations, pas comme des règles serveur.
    const required = PASSWORD_CRITERIA.filter((c) => c.required).map((c) => c.id)
    expect(required).toEqual(['length'])
  })

  it('couvre les 4 critères attendus, dans l’ordre d’affichage', () => {
    expect(PASSWORD_CRITERIA.map((c) => c.id)).toEqual([
      'length',
      'uppercase',
      'digit',
      'special',
    ])
  })
})

describe('evaluatePasswordStrength', () => {
  it('laisse la barre vide tant que rien n’est saisi', () => {
    const result = evaluatePasswordStrength('')
    expect(result.level).toBe('empty')
    expect(result.filledSegments).toBe(0)
    expect(result.metCount).toBe(0)
  })

  it('reste au niveau faible tant que les 8 caractères ne sont pas atteints', () => {
    // Majuscule + chiffre + spécial remplis, mais 7 caractères : le seul
    // critère refusé par le serveur prime sur le reste.
    const result = evaluatePasswordStrength('Ab1!xyz')
    expect(result.met).toMatchObject({
      length: false,
      uppercase: true,
      digit: true,
      special: true,
    })
    expect(result.level).toBe('weak')
    expect(result.filledSegments).toBe(1)
  })

  it('passe à moyen avec 3 critères sur 4', () => {
    const result = evaluatePasswordStrength('Abcdefgh1')
    expect(result.metCount).toBe(3)
    expect(result.level).toBe('medium')
    expect(result.filledSegments).toBe(2)
  })

  it('passe à fort quand les 4 critères sont remplis', () => {
    const result = evaluatePasswordStrength('Abcdefg1!')
    expect(result.metCount).toBe(4)
    expect(result.level).toBe('strong')
    expect(result.filledSegments).toBe(3)
  })

  it('reste faible pour un mot de passe long mais sans variété', () => {
    const result = evaluatePasswordStrength('abcdefghijkl')
    expect(result.met.length).toBe(true)
    expect(result.level).toBe('weak')
  })
})
