'use client'

import Link from 'next/link'
import { useState } from 'react'
import type { AdminAMLPendingItem } from '@/lib/actions/admin-aml.actions'
import AMLEscalatedDecisionPanel from '@/components/AMLEscalatedDecisionPanel'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

interface AdminAMLEscalatedClientProps {
  initialData: AdminAMLPendingItem[]
  initialCount: number
}

function scoreBadgeVariant(score: number): 'destructive' | 'warning' | 'secondary' {
  if (score >= 0.7) return 'destructive'
  if (score >= 0.4) return 'warning'
  return 'secondary'
}

export default function AdminAMLEscalatedClient({
  initialData,
  initialCount,
}: AdminAMLEscalatedClientProps) {
  const [items, setItems] = useState<AdminAMLPendingItem[]>(initialData)
  const [count, setCount] = useState(initialCount)
  const [selected, setSelected] = useState<AdminAMLPendingItem | null>(null)

  const removeFromList = (transferId: string) => {
    setItems((prev) => prev.filter((i) => i.transfer_id !== transferId))
    setCount((c) => Math.max(0, c - 1))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-24 font-bold text-gray-900">Revue AML — Escaladés</h1>
          <p className="text-14 text-gray-500 mt-1">
            {count} dossier{count !== 1 ? 's' : ''} en revue de second niveau
          </p>
        </div>
        <Link href="/admin/aml" className="text-13 font-medium text-blue-600 hover:underline">
          ← Retour à la file d&apos;attente
        </Link>
      </div>

      <Card>
        <CardHeader className="sr-only">
          <CardTitle>Dossiers escaladés</CardTitle>
          <CardDescription>Transferts en attente de revue de second niveau</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          {items.length === 0 ? (
            <div className="flex items-center justify-center py-16 text-gray-400 text-14">
              Aucun dossier escaladé.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="px-6">Référence</TableHead>
                  <TableHead>Score (priorité)</TableHead>
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
        <AMLEscalatedDecisionPanel
          transferId={selected.transfer_id}
          onClose={() => setSelected(null)}
          onDecided={() => removeFromList(selected.transfer_id)}
        />
      )}
    </div>
  )
}
