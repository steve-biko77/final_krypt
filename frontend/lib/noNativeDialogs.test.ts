import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'fs'
import { extname, join } from 'path'

// Correctif shadcn/ui (Dialog) — recherche statique garantissant qu'aucun
// window.confirm()/window.alert() natif ne réapparaît dans le code source
// (l'unique occurrence, l'annulation de transfert, a été remplacée par un
// vrai Dialog — voir app/(root)/(protected)/transfer/[id]/page.tsx).
const ROOT = join(__dirname, '..')
const SCAN_DIRS = ['app', 'components', 'lib']
const IGNORED_DIR_NAMES = new Set(['node_modules', '.next'])

function collectSourceFiles(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (IGNORED_DIR_NAMES.has(entry)) continue
    const full = join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      collectSourceFiles(full, acc)
    } else if (['.ts', '.tsx'].includes(extname(full)) && !/\.test\.tsx?$/.test(full)) {
      acc.push(full)
    }
  }
  return acc
}

describe('Aucun window.confirm()/alert() natif ne subsiste', () => {
  it('ne trouve aucun appel window.confirm(...) ou window.alert(...) dans le code source applicatif', () => {
    const files = SCAN_DIRS.flatMap((d) => collectSourceFiles(join(ROOT, d)))
    const offenders = files.filter((file) => {
      const content = readFileSync(file, 'utf-8')
      return /window\.confirm\(|window\.alert\(/.test(content)
    })

    expect(offenders).toEqual([])
  })
})
