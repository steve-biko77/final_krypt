'use client'

import Link from 'next/link'
import { useState } from 'react'
import type { AdminAMLPendingItem } from '@/lib/actions/admin-aml.actions'
import AMLDecisionPanel from '@/components/AMLDecisionPanel'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

interface AdminAMLClientProps {
  initialData: AdminAMLPendingItem[]
  initialCount: number
}

// Refonte frontend (partie 4a/4) — mêmes seuils que le score affiché dans
// AMLDecisionPanel (Couche 3, seuils_production.md §2) : uniquement pour
// hiérarchiser visuellement la file, jamais un critère de décision.
function scoreBadgeVariant(score: number): 'destructive' | 'warning' | 'secondary' {
  if (score >= 0.7) return 'destructive'
  if (score >= 0.4) return 'warning'
  return 'secondary'
}

export default function AdminAMLClient({ initialData, initialCount }: AdminAMLClientProps) {
  const [items, setItems] = useState<AdminAMLPendingItem[]>(initialData)
  const [count, setCount] = useState(initialCount)
  const [selected, setSelected] = useState<AdminAMLPendingItem | null>(null)

  const removeFromList = (transferId: string) => {
    setItems((prev) => prev.filter((i) => i.transfer_id !== transferId))
    setCount((c) => Math.max(0, c - 1))
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-24 font-bold text-gray-900">Revue AML — En attente</h1>
          <p className="text-14 text-gray-500 mt-1">
            {count} transfert{count !== 1 ? 's' : ''} · trié par signal de priorité décroissant
          </p>
        </div>
        <div className="flex flex-wrap gap-4">
          <Link
            href="/admin/aml/escalated"
            className="text-13 font-medium text-blue-600 hover:underline"
          >
            Voir les dossiers escaladés →
          </Link>
          <Link
            href="/admin/aml/hard-block"
            className="text-13 font-medium text-red-600 hover:underline"
          >
            Voir les alertes HARD_BLOCK →
          </Link>
          <Link
            href="/admin/aml/daily-report"
            className="text-13 font-medium text-gray-700 hover:underline"
          >
            Rapport journalier →
          </Link>
        </div>
      </div>

      <Card>
        <CardHeader className="sr-only">
          <CardTitle>File d&apos;attente AML</CardTitle>
          <CardDescription>Transferts en attente de revue de premier niveau</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          {items.length === 0 ? (
            <div className="flex items-center justify-center py-16 text-gray-400 text-14">
              Aucun transfert en attente de revue.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="px-6">Référence</TableHead>
                  <TableHead>
                    <Tooltip>
                      <TooltipTrigger className="cursor-help underline decoration-dotted underline-offset-2">
                        Score (priorité)
                      </TooltipTrigger>
                      <TooltipContent>
                        Priorise l&apos;affichage — jamais un critère de décision.
                      </TooltipContent>
                    </Tooltip>
                  </TableHead>
                  <TableHead>OFAC</TableHead>
                  <TableHead>Règles déclenchées</TableHead>
                  <TableHead className="px-6">Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow
                    key={item.transfer_id}
                    onClick={() => setSelected(item)}
                    className="cursor-pointer"
                  >
                    <TableCell className="px-6 font-mono text-12 text-gray-700">
                      {item.transfer_id}
                    </TableCell>
                    <TableCell>
                      <Badge variant={scoreBadgeVariant(item.tag_ml_score)}>
                        {Math.round(item.tag_ml_score * 100)}%
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {item.ofac_match ? (
                        <Badge variant="destructive">Match</Badge>
                      ) : (
                        <Badge variant="secondary">—</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-gray-700 whitespace-normal">
                      {item.triggered_rules.length > 0 ? item.triggered_rules.join(', ') : '—'}
                    </TableCell>
                    <TableCell className="px-6 text-gray-500">
                      {item.created_at ? new Date(item.created_at).toLocaleDateString('fr-FR') : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {selected && (
        <AMLDecisionPanel
          transferId={selected.transfer_id}
          onClose={() => setSelected(null)}
          onDecided={() => removeFromList(selected.transfer_id)}
        />
      )}
    </div>
  )
}
