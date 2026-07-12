'use client'

import { useState, useTransition } from 'react'
import Link from 'next/link'
import { AlertCircle, Archive, Download, ExternalLink } from 'lucide-react'
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

const COUNTER_LABELS: { key: keyof AdminAMLDailyReport['counts']; label: string }[] = [
  { key: 'approve', label: 'Approuvés' },
  { key: 'reject', label: 'Rejetés' },
  { key: 'escalate', label: 'Escaladés' },
  { key: 'hard_block_documented', label: 'HARD_BLOCK documentés' },
  { key: 'hard_block_frozen', label: 'Comptes gelés' },
  { key: 'hard_block_tracfin_generated', label: 'Déclarations TRACFIN' },
]

const POLYGONSCAN_TX = 'https://amoy.polygonscan.com/tx'

export default function AdminAMLDailyReportClient({
  initialReport,
}: AdminAMLDailyReportClientProps) {
  const [date, setDate] = useState(initialReport.date)
  const [report, setReport] = useState<AdminAMLDailyReport>(initialReport)
  const [error, setError] = useState<string | null>(null)
  const [confirmingArchive, setConfirmingArchive] = useState(false)
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

  const handleDateChange = (newDate: string) => {
    setDate(newDate)
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
    setError(null)
    startTransition(async () => {
      try {
        const result = await archiveAdminAMLDailyReport(date)
        setArchiveResult(result)
        setConfirmingArchive(false)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Une erreur est survenue.')
        setConfirmingArchive(false)
      }
    })
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
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
        <label className="text-13 font-medium text-gray-700">
          Date
          <input
            type="date"
            value={date}
            max={initialReport.date}
            onChange={(e) => handleDateChange(e.target.value)}
            className="ml-2 border border-gray-300 rounded-lg px-3 py-1.5 text-14 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </label>
      </div>

      {error && (
        <p className="text-13 text-red-600 mb-4 flex items-center gap-1">
          <AlertCircle size={14} /> {error}
        </p>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
        {COUNTER_LABELS.map(({ key, label }) => (
          <div key={key} className="rounded-xl border border-gray-200 p-4">
            <p className="text-24 font-bold text-gray-900">{report.counts[key]}</p>
            <p className="text-12 text-gray-500">{label}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <button
          onClick={handleExportCSV}
          disabled={isPending}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800 text-white text-13 font-semibold hover:bg-gray-900 disabled:opacity-50 transition"
        >
          <Download size={14} />
          Exporter CSV
        </button>

        {!confirmingArchive ? (
          <button
            onClick={() => setConfirmingArchive(true)}
            disabled={isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-orange-600 text-white text-13 font-semibold hover:bg-orange-700 disabled:opacity-50 transition"
          >
            <Archive size={14} />
            Archiver
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-13 text-gray-700">Confirmer l&apos;archivage du {date} ?</span>
            <button
              onClick={handleArchive}
              disabled={isPending}
              className="px-3 py-1.5 rounded-lg bg-orange-600 text-white text-13 font-semibold hover:bg-orange-700 disabled:opacity-50 transition"
            >
              Confirmer
            </button>
            <button
              onClick={() => setConfirmingArchive(false)}
              disabled={isPending}
              className="px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 text-13 font-semibold hover:bg-gray-200 transition"
            >
              Annuler
            </button>
          </div>
        )}
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

      <div className="overflow-x-auto rounded-xl border border-gray-200">
        <table className="w-full text-left text-14">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 font-semibold text-gray-600">Horodatage</th>
              <th className="px-4 py-3 font-semibold text-gray-600">Admin</th>
              <th className="px-4 py-3 font-semibold text-gray-600">Action</th>
              <th className="px-4 py-3 font-semibold text-gray-600">Référence</th>
              <th className="px-4 py-3 font-semibold text-gray-600">Tx Polygon</th>
            </tr>
          </thead>
          <tbody>
            {report.decisions.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400 text-14">
                  Aucune décision pour cette date.
                </td>
              </tr>
            ) : (
              report.decisions.map((d) => (
                <tr key={d.id} className="border-b border-gray-100">
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(d.created_at).toLocaleString('fr-FR')}
                  </td>
                  <td className="px-4 py-3 text-gray-700">{d.admin_email ?? d.admin_id}</td>
                  <td className="px-4 py-3 text-gray-700">{d.action}</td>
                  <td className="px-4 py-3 font-mono text-12 text-gray-700">
                    {d.transaction_id}
                  </td>
                  <td className="px-4 py-3">
                    {d.tx_hash ? (
                      <a
                        href={`${POLYGONSCAN_TX}/${d.tx_hash}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline text-12"
                      >
                        Voir
                      </a>
                    ) : (
                      <span className="text-gray-400 text-12">—</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
