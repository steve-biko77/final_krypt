import { describe, expect, it } from 'vitest';
import { deriveRouteState } from './transferRoute';
import type { TimelineStep } from './transferTimeline';

function step(key: string, status: TimelineStep['status']): TimelineStep {
  return { key: key as TimelineStep['key'], label: key, description: '', status };
}

describe('deriveRouteState', () => {
  it('progression 0 tant que seule la 1ère étape est active', () => {
    const steps = [step('sent', 'active'), step('compliance', 'pending'), step('payment', 'pending')];
    expect(deriveRouteState(steps)).toEqual({ progress: 0, state: 'active' });
  });

  it('avance au fil des étapes terminées', () => {
    const steps = [step('sent', 'done'), step('compliance', 'active'), step('payment', 'pending')];
    expect(deriveRouteState(steps)).toEqual({ progress: 0.5, state: 'active' });
  });

  it('progression 1 et état done quand toutes les étapes sont terminées', () => {
    const steps = [step('sent', 'done'), step('compliance', 'done'), step('payment', 'done')];
    expect(deriveRouteState(steps)).toEqual({ progress: 1, state: 'done' });
  });

  it('état error à la position de la première étape en erreur', () => {
    const steps = [step('sent', 'done'), step('compliance', 'error'), step('payment', 'pending')];
    expect(deriveRouteState(steps)).toEqual({ progress: 0.5, state: 'error' });
  });

  it('état cancelled à la position de la première étape annulée', () => {
    const steps = [step('sent', 'done'), step('compliance', 'cancelled'), step('payment', 'pending')];
    expect(deriveRouteState(steps)).toEqual({ progress: 0.5, state: 'cancelled' });
  });
});
