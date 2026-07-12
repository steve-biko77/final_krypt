import { defineConfig } from 'vitest/config'

// KRYP-27 — setup minimal : les tests ne couvrent que de la logique TypeScript
// pure (mapping timeline + décision de polling), sans rendu React ni jsdom.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['lib/**/*.test.ts'],
  },
})
