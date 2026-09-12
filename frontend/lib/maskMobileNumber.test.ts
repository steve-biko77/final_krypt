import { describe, expect, it } from 'vitest'
import { maskMobileNumber } from './maskMobileNumber'

describe('maskMobileNumber', () => {
  it('masque un numéro camerounais avec préfixe international', () => {
    expect(maskMobileNumber('+237699000002')).toBe('+237 69• ••• •02')
  })

  it('masque un numéro sans le +', () => {
    expect(maskMobileNumber('237655000089')).toBe('+237 65• ••• •89')
  })

  it('masque un numéro local sans préfixe pays', () => {
    expect(maskMobileNumber('699000002')).toBe('69• ••• •02')
  })

  it('gère les espaces dans le numéro source', () => {
    expect(maskMobileNumber('+237 699 000 002')).toBe('+237 69• ••• •02')
  })

  it('retombe sur un masquage générique pour un format non standard', () => {
    expect(maskMobileNumber('+33612345678')).toBe('33•••••••78')
  })

  it('renvoie le numéro tel quel si trop court pour être masqué', () => {
    expect(maskMobileNumber('123')).toBe('123')
  })
})
