/**
 * KRYP-27 — Logique pure de projection statut backend → timeline visuelle.
 *
 * Ce module est volontairement sans dépendance React / DOM pour être testable en
 * isolation (voir transferTimeline.test.ts). Aucun nom de statut backend ne doit
 * jamais fuiter vers l'UI : seule la copie orientée utilisateur définie ici est
 * exposée.
 */

/** Les 10 statuts réels de TransactionStatus (backend/contexts/transfer/domain/entities.py). */
export type TransactionStatus =
  | 'DRAFT'
  | 'PENDING_AML'
  | 'AML_BLOCKED'
  | 'AML_PENDING_REVIEW'
  | 'PROCESSING'
  | 'ESCROWED'
  | 'ESCROW_FAILED'
  | 'DELIVERED'
  | 'PAYMENT_FAILED'
  | 'PAYOUT_FAILED';

export type StepStatus = 'done' | 'active' | 'pending' | 'error';

export type TimelineStepKey =
  | 'sent'
  | 'compliance'
  | 'payment'
  | 'payout'
  | 'delivered';

export interface TimelineStep {
  key: TimelineStepKey;
  label: string;
  description: string;
  status: StepStatus;
  /** ISO timestamp, uniquement pour les étapes atteintes (done/active/error). */
  timestamp?: string;
  /** Hash on-chain réel — jamais un placeholder. Seule l'étape 3 (escrow) en a un. */
  txHash?: string;
}

/**
 * Statuts terminaux : le polling doit s'arrêter dès qu'ils sont atteints.
 * (AML_BLOCKED, ESCROW_FAILED, PAYMENT_FAILED, DELIVERED, PAYOUT_FAILED.)
 */
const TERMINAL_STATUSES: ReadonlySet<TransactionStatus> = new Set<TransactionStatus>([
  'AML_BLOCKED',
  'ESCROW_FAILED',
  'PAYMENT_FAILED',
  'DELIVERED',
  'PAYOUT_FAILED',
]);

/** True si le statut est terminal (arrêter le polling). */
export function isTerminalStatus(status: TransactionStatus): boolean {
  return TERMINAL_STATUSES.has(status);
}

/** Overall badge utilisateur (jamais un statut backend brut). */
export type OverallState = 'in_progress' | 'delivered' | 'error';

export function overallState(status: TransactionStatus): OverallState {
  if (status === 'DELIVERED') return 'delivered';
  if (
    status === 'AML_BLOCKED' ||
    status === 'ESCROW_FAILED' ||
    status === 'PAYMENT_FAILED' ||
    status === 'PAYOUT_FAILED'
  ) {
    return 'error';
  }
  return 'in_progress';
}

export function overallStateLabel(status: TransactionStatus): string {
  switch (overallState(status)) {
    case 'delivered':
      return 'Livré';
    case 'error':
      return status === 'AML_BLOCKED' ? 'Bloqué' : 'Échec';
    default:
      return 'En cours';
  }
}

const OPERATOR_LABEL: Record<string, string> = {
  MTN_MOMO: 'MTN MoMo',
  ORANGE_MONEY: 'Orange Money',
};

export function operatorLabel(operator?: string | null): string {
  if (!operator) return 'Mobile Money';
  return OPERATOR_LABEL[operator] ?? 'Mobile Money';
}

/** Prénom du bénéficiaire (première partie du nom complet). */
function firstName(fullName: string): string {
  const trimmed = (fullName ?? '').trim();
  if (!trimmed) return 'le bénéficiaire';
  return trimmed.split(/\s+/)[0];
}

export interface TimelineInput {
  status: TransactionStatus;
  beneficiaryName: string;
  operator?: string | null;
  escrowTxHash?: string | null;
  payoutReference?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  escrowedAt?: string | null;
}

/**
 * Projette un statut backend sur les 5 étapes visuelles validées.
 *
 * Table de correspondance (voir ticket KRYP-27) — implémentée exactement.
 * Un timestamp n'est posé que sur les étapes atteintes. Le lien Polygonscan
 * (txHash) n'est jamais posé sur une étape sans preuve on-chain réelle : seule
 * l'étape 3 reçoit escrow_tx_hash, l'étape 5 n'expose que payout_reference en
 * texte brut (aucun hash per-transaction n'est persisté pour l'AuditTrail).
 */
export function buildTimeline(input: TimelineInput): TimelineStep[] {
  const {
    status,
    beneficiaryName,
    operator,
    escrowTxHash,
    payoutReference,
    createdAt,
    updatedAt,
    escrowedAt,
  } = input;

  const opLabel = operatorLabel(operator);
  const prenom = firstName(beneficiaryName);

  // Étape 1 — Envoyé : toujours au moins done sauf DRAFT (active).
  const step1: TimelineStep = {
    key: 'sent',
    label: 'Transfert envoyé',
    description: 'Votre demande de transfert a été enregistrée',
    status: status === 'DRAFT' ? 'active' : 'done',
    timestamp: createdAt ?? undefined,
  };

  // Étape 2 — Conformité.
  const step2 = buildComplianceStep(status, updatedAt);

  // Étape 3 — Paiement / escrow.
  const step3 = buildPaymentStep(status, escrowTxHash, escrowedAt, updatedAt);

  // Étape 4 — Mobile Money.
  const step4 = buildPayoutStep(status, opLabel, updatedAt);

  // Étape 5 — Livré.
  const step5 = buildDeliveredStep(status, prenom, payoutReference, updatedAt);

  return [step1, step2, step3, step4, step5];
}

function buildComplianceStep(
  status: TransactionStatus,
  updatedAt?: string | null,
): TimelineStep {
  const base = {
    key: 'compliance' as const,
    label: 'Vérification de conformité',
  };

  if (status === 'DRAFT') {
    return { ...base, description: 'Contrôles de sécurité et de conformité', status: 'pending' };
  }
  if (status === 'PENDING_AML' || status === 'AML_PENDING_REVIEW') {
    // AML_PENDING_REVIEW reste "active" (jamais un état d'erreur) : la revue
    // manuelle peut encore se résoudre favorablement, le polling continue.
    return {
      ...base,
      description: 'Contrôles de sécurité et de conformité en cours',
      status: 'active',
      timestamp: updatedAt ?? undefined,
    };
  }
  if (status === 'AML_BLOCKED') {
    return {
      ...base,
      label: 'Transfert bloqué',
      description: 'Contactez le support pour plus d’informations',
      status: 'error',
      timestamp: updatedAt ?? undefined,
    };
  }
  // PROCESSING, ESCROWED, ESCROW_FAILED, PAYMENT_FAILED, DELIVERED, PAYOUT_FAILED
  return {
    ...base,
    description: 'Contrôles de sécurité validés',
    status: 'done',
    timestamp: updatedAt ?? undefined,
  };
}

function buildPaymentStep(
  status: TransactionStatus,
  escrowTxHash?: string | null,
  escrowedAt?: string | null,
  updatedAt?: string | null,
): TimelineStep {
  const base = { key: 'payment' as const, label: 'Paiement sécurisé' };

  switch (status) {
    case 'DRAFT':
    case 'PENDING_AML':
    case 'AML_BLOCKED':
    case 'AML_PENDING_REVIEW':
      return { ...base, description: 'En attente de paiement', status: 'pending' };
    case 'PROCESSING':
      return {
        ...base,
        description: 'Carte bancaire débitée · Escrow en cours de verrouillage',
        status: 'active',
        timestamp: updatedAt ?? undefined,
      };
    case 'PAYMENT_FAILED':
      return {
        ...base,
        label: 'Paiement refusé',
        description: 'Le paiement par carte a été refusé',
        status: 'error',
        timestamp: updatedAt ?? undefined,
      };
    case 'ESCROW_FAILED':
      return {
        ...base,
        label: 'Erreur de traitement',
        description: 'Une erreur est survenue, notre équipe a été alertée',
        status: 'error',
        timestamp: updatedAt ?? undefined,
      };
    // ESCROWED, DELIVERED, PAYOUT_FAILED : escrow verrouillé, hash disponible.
    default:
      return {
        ...base,
        description: 'Carte bancaire débitée · Escrow verrouillé',
        status: 'done',
        timestamp: escrowedAt ?? undefined,
        txHash: escrowTxHash ?? undefined,
      };
  }
}

function buildPayoutStep(
  status: TransactionStatus,
  opLabel: string,
  updatedAt?: string | null,
): TimelineStep {
  const base = { key: 'payout' as const, label: 'Envoi Mobile Money' };

  switch (status) {
    case 'ESCROWED':
      return {
        ...base,
        description: `Envoi vers le portefeuille ${opLabel}`,
        status: 'active',
        timestamp: updatedAt ?? undefined,
      };
    case 'PAYOUT_FAILED':
      return {
        ...base,
        label: 'Échec de livraison',
        description: '3 tentatives Mobile Money · remboursement en cours',
        status: 'error',
        timestamp: updatedAt ?? undefined,
      };
    case 'DELIVERED':
      return {
        ...base,
        description: `Fonds envoyés vers le portefeuille ${opLabel}`,
        status: 'done',
        timestamp: updatedAt ?? undefined,
      };
    // DRAFT, PENDING_AML, AML_*, PROCESSING, PAYMENT_FAILED, ESCROW_FAILED
    default:
      return { ...base, description: `Envoi vers le portefeuille ${opLabel}`, status: 'pending' };
  }
}

function buildDeliveredStep(
  status: TransactionStatus,
  prenom: string,
  payoutReference?: string | null,
  updatedAt?: string | null,
): TimelineStep {
  const base = { key: 'delivered' as const, label: 'Fonds livrés' };

  if (status === 'DELIVERED') {
    const ref = payoutReference ? ` · Réf. ${payoutReference}` : '';
    return {
      ...base,
      description: `Reçus par ${prenom}${ref}`,
      status: 'done',
      timestamp: updatedAt ?? undefined,
    };
  }
  return { ...base, description: 'Fonds crédités sur le compte Mobile Money', status: 'pending' };
}
