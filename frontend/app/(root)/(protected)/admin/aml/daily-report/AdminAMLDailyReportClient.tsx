'use client'

import { useState, useTransition } from 'react'
import Link from 'next/link'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { AlertCircle, Archive, CalendarIcon, Download, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  archiveAdminAMLDailyReport,
  exportAdminAMLDailyReportCSV,
  getAdminAMLDailyReport,
  type AdminAMLDailyReport,
  type AdminAMLDailyReportArchiveResult,
} from '@/lib/actions/admin-aml.actions'

interface AdminAMLDailyReportClientProps {
  initialReport: AdminAMLDailyReport
}

const COUNTER_LABELS: {
  key: keyof AdminAMLDailyReport['counts']
  label: string
  variant: 'success' | 'destructive' | 'warning' | 'secondary'
}[] = [
  { key: 'approve', label: 'Approuvés', variant: 'success' },
  { key: 'reject', label: 'Rejetés', variant: 'destructive' },
  { key: 'escalate', label: 'Escaladés', variant: 'warning' },
  { key: 'hard_block_documented', label: 'HARD_BLOCK documentés', variant: 'secondary' },
  { key: 'hard_block_frozen', label: 'Comptes gelés', variant: 'secondary' },
  { key: 'hard_block_tracfin_generated', label: 'Déclarations TRACFIN', variant: 'secondary' },
]

const POLYGONSCAN_TX = 'https://amoy.polygonscan.com/tx'

// Les dates de rapport sont des jours calendaires (YYYY-MM-DD, sans fuseau) —
// construction manuelle plutôt que `new Date(iso)` pour éviter un décalage
// de jour en UTC- (parsing ISO nu = minuit UTC, pas minuit local).
function parseISODate(value: string): Date {
  const [y, m, d] = value.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function toISODate(date: Date): string {
  return format(date, 'yyyy-MM-dd')
}

export default function AdminAMLDailyReportClient({
  initialReport,
}: AdminAMLDailyReportClientProps) {
  const [date, setDate] = useState(initialReport.date)
  const [report, setReport] = useState<AdminAMLDailyReport>(initialReport)
  const [error, setError] = useState<string | null>(null)
  const [archiveError, setArchiveError] = useState<string | null>(null)
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [datePickerOpen, setDatePickerOpen] = useState(false)
  const [archiveResult, setArchiveResult] = useState<AdminAMLDailyReportArchiveResult | null>(null)
  const [isPending, startTransition] = useTransition()

  const loadReport = (newDate: string) => {
    setError(null)
    setArchiveResult(null)
    startTransition(async () => {
      try {
        const data = await getAdminAMLDailyReport(newDate)
        setReport(data)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Une erreur est survenue.')
      }
    })
  }

  const handleDateSelect = (selected: Date | undefined) => {
    if (!selected) return
    const newDate = toISODate(selected)
    setDate(newDate)
    setDatePickerOpen(false)
    loadReport(newDate)
  }

  const handleExportCSV = () => {
    setError(null)
    startTransition(async () => {
      try {
        const { filename, content } = await exportAdminAMLDailyReportCSV(date)
        const blob = new Blob(['﻿' + content], { type: 'text/csv;charset=utf-8;' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Une erreur est survenue.')
      }
    })
  }

  const handleArchive = () => {
    setArchiveError(null)
    startTransition(async () => {
      try {
        const result = await archiveAdminAMLDailyReport(date)
        setArchiveResult(result)
        setArchiveOpen(false)
        toast.success('Rapport archivé')
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Une erreur est survenue.'
        setArchiveError(message)
        toast.error("Échec de l'archivage", { description: message })
      }
    })
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-24 font-bold text-gray-900">Rapport de fin de journée</h1>
          <p className="text-14 text-gray-500 mt-1">
            {report.total_decisions} décision{report.total_decisions !== 1 ? 's' : ''} au{' '}
            {new Date(report.date).toLocaleDateString('fr-FR')}
          </p>
        </div>
        <Link href="/admin/aml" className="text-13 font-medium text-blue-600 hover:underline">
          ← Retour à la file d&apos;attente
        </Link>
      </div>

      <div className="flex items-center gap-3 mb-6">
        <Popover open={datePickerOpen} onOpenChange={setDatePickerOpen}>
          <PopoverTrigger asChild>
            <Button type="button" variant="outline" size="sm" disabled={isPending}>
              <CalendarIcon size={14} />
              {format(parseISODate(date), 'd MMMM yyyy', { locale: fr })}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar
              mode="single"
              selected={parseISODate(date)}
              onSelect={handleDateSelect}
              disabled={{ after: parseISODate(initialReport.date) }}
              autoFocus
            />
          </PopoverContent>
        </Popover>
      </div>

      {error && (
        <p className="text-13 text-red-600 mb-4 flex items-center gap-1">
          <AlertCircle size={14} /> {error}
        </p>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
        {COUNTER_LABELS.map(({ key, label, variant }) => (
          <Card key={key} className="min-w-0">
            <CardContent className="px-4 flex flex-col gap-1.5">
              <p className="text-24 font-bold text-gray-900">{report.counts[key]}</p>
              {/* whitespace-normal (au lieu du nowrap par défaut du Badge) —
                  les libellés longs ("HARD_BLOCK documentés") doivent pouvoir
                  passer à la ligne plutôt que forcer la colonne de la grille
                  à s'élargir au-delà de 1fr (débordement à 375px). */}
              <Badge variant={variant} className="w-fit whitespace-normal text-left">
                {label}
              </Badge>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <Button type="button" onClick={handleExportCSV} disabled={isPending} variant="secondary">
          <Download size={14} />
          Exporter CSV
        </Button>

        <Dialog
          open={archiveOpen}
          onOpenChange={(next) => {
            setArchiveOpen(next)
            if (next) setArchiveError(null)
          }}
        >
          <DialogTrigger asChild>
            <Button
              type="button"
              disabled={isPending}
              className="bg-orange-600 hover:bg-orange-700 text-white"
            >
              <Archive size={14} />
              Archiver
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Archiver le rapport du {date} ?</DialogTitle>
              <DialogDescription>
                L&apos;archivage est définitif pour cette date : une fois archivé, ce rapport ne
                pourra plus être ré-archivé. Une référence Polygon sera générée pour attester son
                intégrité.
              </DialogDescription>
            </DialogHeader>
            {archiveError && (
              <p className="text-13 text-red-600 flex items-center gap-1">
                <AlertCircle size={14} /> {archiveError}
              </p>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setArchiveOpen(false)}
                disabled={isPending}
              >
                Annuler
              </Button>
              <Button
                type="button"
                onClick={handleArchive}
                disabled={isPending}
                className="bg-orange-600 hover:bg-orange-700 text-white"
              >
                {isPending ? 'Archivage…' : "Confirmer l'archivage"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {archiveResult && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 mb-6 space-y-1">
          <p className="text-13 font-medium text-green-800">
            Rapport du {archiveResult.date} archivé.
          </p>
          {archiveResult.polygon_batch_tx_hash ? (
            <a
              href={`${POLYGONSCAN_TX}/${archiveResult.polygon_batch_tx_hash}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-13 font-medium text-blue-600 hover:underline"
            >
              <ExternalLink size={14} />
              Référence Polygon : batch {archiveResult.polygon_batch_id}
            </a>
          ) : (
            <p className="text-12 text-green-700">
              Aucun batch Polygon disponible pour cette date.
            </p>
          )}
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="px-4">Horodatage</TableHead>
            <TableHead>Admin</TableHead>
            <TableHead>Action</TableHead>
            <TableHead>Référence</TableHead>
            <TableHead className="px-4">Tx Polygon</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {report.decisions.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="px-4 py-8 text-center text-gray-400">
                Aucune décision pour cette date.
              </TableCell>
            </TableRow>
          ) : (
            report.decisions.map((d) => (
              <TableRow key={d.id}>
                <TableCell className="px-4 text-gray-500">
                  {new Date(d.created_at).toLocaleString('fr-FR')}
                </TableCell>
                <TableCell className="text-gray-700">{d.admin_email ?? d.admin_id}</TableCell>
                <TableCell className="text-gray-700">{d.action}</TableCell>
                <TableCell className="px-4 font-mono text-12 text-gray-700">
                  {d.transaction_id}
                </TableCell>
                <TableCell className="px-4">
                  {d.tx_hash ? (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <a
                          href={`${POLYGONSCAN_TX}/${d.tx_hash}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline text-12"
                        >
                          Voir
                        </a>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="max-w-56">
                          Preuve on-chain de cette décision, vérifiable publiquement sur
                          Polygonscan.
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    <span className="text-gray-400 text-12">—</span>
                  )}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  )
}
