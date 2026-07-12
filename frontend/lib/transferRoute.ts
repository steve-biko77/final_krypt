/**
 * Refonte frontend (partie 1/4) — logique pure de projection des étapes de la
 * timeline (KRYP-27, `lib/transferTimeline.ts`) vers une progression 0..1 le
 * long d'une route origine → destination.
 *
 * Réutilise volontairement `TimelineStep[]` comme SEULE source de vérité :
 * TransferRouteIndicator (nouveau, horizontal) et TransferTimeline (existant,
 * vertical détaillé) partagent donc exactement la même dérivation de statut
 * plutôt que d'avoir deux implémentations divergentes du même concept.
 */
import type { TimelineStep } from './transferTimeline';

export type RouteState = 'active' | 'done' | 'error' | 'cancelled';

export interface RouteProgress {
  /** 0..1 le long de la route. */
  progress: number;
  state: RouteState;
}

export function deriveRouteState(steps: TimelineStep[]): RouteProgress {
  const total = steps.length;
  if (total <= 1) {
    return { progress: 1, state: 'done' };
  }

  const errorIndex = steps.findIndex((s) => s.status === 'error');
  if (errorIndex !== -1) {
    return { progress: errorIndex / (total - 1), state: 'error' };
  }

  const cancelledIndex = steps.findIndex((s) => s.status === 'cancelled');
  if (cancelledIndex !== -1) {
    return { progress: cancelledIndex / (total - 1), state: 'cancelled' };
  }

  const doneCount = steps.filter((s) => s.status === 'done').length;
  if (doneCount === total) {
    return { progress: 1, state: 'done' };
  }

  const activeIndex = steps.findIndex((s) => s.status === 'active');
  const progress = (activeIndex !== -1 ? activeIndex : doneCount) / (total - 1);
  return { progress, state: 'active' };
}
