import type { ReactElement, ReactNode } from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { TooltipProvider } from '@/components/ui/tooltip'

// Correctif shadcn/ui — tout composant rendant un <Tooltip> exige un
// TooltipProvider ancêtre (fourni globalement par app/layout.tsx en
// production, absent des rendus isolés de test). Wrapper à réutiliser plutôt
// que de dupliquer <TooltipProvider> dans chaque fichier de test concerné.
function AllProviders({ children }: { children: ReactNode }) {
  return <TooltipProvider>{children}</TooltipProvider>
}

export function renderWithProviders(ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) {
  return render(ui, { wrapper: AllProviders, ...options })
}

export * from '@testing-library/react'
