import { fileURLToPath } from 'url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Environnement jsdom (nécessaire au rendu React des tests de composants,
// refonte frontend partie 1/4) — inoffensif pour les tests de logique pure
// existants (lib/**/*.test.ts, KRYP-27) qui n'utilisent aucune API DOM.
// Plugin React requis pour le transform JSX des *.test.tsx ; alias "@/*" repris
// manuellement de tsconfig.json (non lu automatiquement par Vitest).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('.', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    include: ['lib/**/*.test.ts', 'components/**/*.test.tsx'],
  },
})
