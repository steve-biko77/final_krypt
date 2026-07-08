import { describe, it, expect } from 'vitest'

import {
  buildTimeline,
  isTerminalStatus,
  overallState,
  overallStateLabel,
  type TransactionStatus,
  type StepStatus,
} from './transferTimeline'

const ALL_STATUSES: TransactionStatus[] = [
  'DRAFT',
  'PENDING_AML',
  'AML_BLOCKED',
  'AML_PENDING_REVIEW',
  'PROCESSING',
  'ESCROWED',
  'ESCROW_FAILED',
  'DELIVERED',
  'PAYMENT_FAILED',
  'PAYOUT_FAILED',
]

const BASE = {
  beneficiaryName: 'Jean Mbarga',
  operator: 'MTN_MOMO',
  escrowTxHash: '0xdeadbeef00112233',
  payoutReference: 'mtn-ref-42',
  createdAt: '2026-07-04T10:00:00Z',
  updatedAt: '2026-07-04T10:05:00Z',
  escrowedAt: '2026-07-04T10:03:00Z',
}

function stepStatuses(status: TransactionStatus): StepStatus[] {
  return buildTimeline({ ...BASE, status }).map((s) => s.status)
}

describe('buildTimeline — mapping statut → 5 étapes visuelles', () => {
  // Table de correspondance exacte du ticket KRYP-27.
  const EXPECTED: Record<TransactionStatus, StepStatus[]> = {
    DRAFT: ['active', 'pending', 'pending', 'pending', 'pending'],
    PENDING_AML: ['done', 'active', 'pending', 'pending', 'pending'],
    AML_BLOCKED: ['done', 'error', 'pending', 'pending', 'pending'],
    AML_PENDING_REVIEW: ['done', 'active', 'pending', 'pending', 'pending'],
    PROCESSING: ['done', 'done', 'active', 'pending', 'pending'],
    ESCROWED: ['done', 'done', 'done', 'active', 'pending'],
    ESCROW_FAILED: ['done', 'done', 'error', 'pending', 'pending'],
    PAYMENT_FAILED: ['done', 'done', 'error', 'pending', 'pending'],
    DELIVERED: ['done', 'done', 'done', 'done', 'done'],
    PAYOUT_FAILED: ['done', 'done', 'done', 'error', 'pending'],
  }

  for (const status of ALL_STATUSES) {
    it(`${status} produit la bonne séquence d'états`, () => {
      expect(stepStatuses(status)).toEqual(EXPECTED[status])
    })
  }

  it('AML_PENDING_REVIEW ne produit JAMAIS un état error (revue en cours)', () => {
    const steps = buildTimeline({ ...BASE, status: 'AML_PENDING_REVIEW' })
    expect(steps.some((s) => s.status === 'error')).toBe(false)
    expect(steps[1].status).toBe('active')
  })

  it('renvoie toujours exactement 5 étapes', () => {
    for (const status of ALL_STATUSES) {
      expect(buildTimeline({ ...BASE, status })).toHaveLength(5)
    }
  })
})

describe('lien Polygonscan (txHash) — preuve on-chain réelle uniquement', () => {
  it('expose escrow_tx_hash sur l’étape 3 quand escrow verrouillé', () => {
    for (const status of ['ESCROWED', 'DELIVERED', 'PAYOUT_FAILED'] as TransactionStatus[]) {
      const steps = buildTimeline({ ...BASE, status })
      expect(steps[2].txHash).toBe(BASE.escrowTxHash)
    }
  })

  it('n’expose jamais de txHash sur l’étape 5 (aucun hash AuditTrail persisté)', () => {
    for (const status of ALL_STATUSES) {
      const steps = buildTimeline({ ...BASE, status })
      expect(steps[4].txHash).toBeUndefined()
    }
  })

  it('n’expose aucun txHash avant le verrouillage escrow', () => {
    for (const status of ['DRAFT', 'PENDING_AML', 'AML_PENDING_REVIEW', 'PROCESSING'] as TransactionStatus[]) {
      const steps = buildTimeline({ ...BASE, status })
      expect(steps[2].txHash).toBeUndefined()
    }
  })
})

describe('aucune fuite de statut backend dans la copie utilisateur', () => {
  it('aucun label/description ne contient un nom de statut brut', () => {
    for (const status of ALL_STATUSES) {
      const steps = buildTimeline({ ...BASE, status })
      const text = steps.map((s) => `${s.label} ${s.description}`).join(' ')
      for (const raw of ALL_STATUSES) {
        expect(text).not.toContain(raw)
      }
    }
  })

  it('DELIVERED affiche le prénom du bénéficiaire', () => {
    const steps = buildTimeline({ ...BASE, status: 'DELIVERED' })
    expect(steps[4].description).toContain('Jean')
  })
})

describe('isTerminalStatus — arrêt / poursuite du polling', () => {
  const TERMINAL: TransactionStatus[] = [
    'AML_BLOCKED',
    'ESCROW_FAILED',
    'PAYMENT_FAILED',
    'DELIVERED',
    'PAYOUT_FAILED',
  ]
  const NON_TERMINAL: TransactionStatus[] = [
    'DRAFT',
    'PENDING_AML',
    'AML_PENDING_REVIEW',
    'PROCESSING',
    'ESCROWED',
  ]

  for (const status of TERMINAL) {
    it(`${status} est terminal (polling stoppé)`, () => {
      expect(isTerminalStatus(status)).toBe(true)
    })
  }

  for (const status of NON_TERMINAL) {
    it(`${status} n'est pas terminal (polling continue)`, () => {
      expect(isTerminalStatus(status)).toBe(false)
    })
  }

  it('couvre les 10 statuts, sans oubli', () => {
    expect([...TERMINAL, ...NON_TERMINAL].sort()).toEqual([...ALL_STATUSES].sort())
  })
})

describe('overallState / overallStateLabel', () => {
  it('DELIVERED → livré', () => {
    expect(overallState('DELIVERED')).toBe('delivered')
    expect(overallStateLabel('DELIVERED')).toBe('Livré')
  })
  it('AML_BLOCKED → bloqué', () => {
    expect(overallState('AML_BLOCKED')).toBe('error')
    expect(overallStateLabel('AML_BLOCKED')).toBe('Bloqué')
  })
  it('PAYOUT_FAILED → échec', () => {
    expect(overallStateLabel('PAYOUT_FAILED')).toBe('Échec')
  })
  it('PROCESSING → en cours', () => {
    expect(overallState('PROCESSING')).toBe('in_progress')
    expect(overallStateLabel('PROCESSING')).toBe('En cours')
  })
})
