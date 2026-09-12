import { describe, expect, it } from 'vitest'
import { detectMobileMoneyOperator } from './detectMobileMoneyOperator'

describe('detectMobileMoneyOperator', () => {
  it.each([
    ['+237 670 000 002', 'MTN'],
    ['+237650000002', 'MTN'],
    ['237654000002', 'MTN'],
    ['680000002', 'MTN'],
    ['+237684000002', 'MTN'],
  ])('détecte MTN pour %s', (number, expected) => {
    expect(detectMobileMoneyOperator(number)).toBe(expected)
  })

  it.each([
    ['+237699000002', 'ORANGE'],
    ['+237 655 000 002', 'ORANGE'],
    ['237659000002', 'ORANGE'],
    ['685000002', 'ORANGE'],
    ['+237689000002', 'ORANGE'],
  ])('détecte Orange pour %s', (number, expected) => {
    expect(detectMobileMoneyOperator(number)).toBe(expected)
  })

  it.each([
    ['+33612345678', 'un numéro français'],
    ['+237620000002', 'un préfixe camerounais non attribué (62x)'],
    ['12', 'un numéro trop court'],
    ['', 'une chaîne vide'],
  ])('ne détecte rien pour %s (%s)', (number) => {
    expect(detectMobileMoneyOperator(number)).toBeNull()
  })
})
