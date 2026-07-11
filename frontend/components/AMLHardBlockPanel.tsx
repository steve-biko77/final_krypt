'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { AlertCircle, FileText, Lock, FileWarning, X, ExternalLink } from 'lucide-react'
import {
  documentHardBlockCase,
  freezeAccount,
  generateTracfinReport,
  type AdminAMLHardBlockedItem,
} from '@/lib/actions/admin-aml.actions'

interface AMLHardBlockPanelProps {
  item: AdminAMLHardBlockedItem
  onClose: () => void
  onUpdated: (patch: Partial<AdminAMLHardBlockedItem>) => void
}

export default function AMLHardBlockPanel({ item, onClose, onUpdated }: AMLHardBlockPanelProps) {
  const router = useRouter()
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()

  // Les 3 actions sont indépendantes — aucune n'est bloquée par l'état des
  // autres, et aucune ne change le statut HARD_BLOCK du transfert.
  const handleDocument = () => {
    if (!note.trim()) {
      setError('Une note est requise pour documenter ce cas.')
      return
    }
    setError(null)
    startTransition(async () => {
      try {
        await documentHardBlockCase(item.transfer_id, note)
        setNote('')
        onUpdated({ is_documented: true })
        router.refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Une erreur est survenue.')
      }
    })
  }

  const handleFreeze = () => {
    setError(null)
    startTransition(async () => {
      try {
        await freezeAccount(item.transfer_id)
        onUpdated({ account_frozen: true })
        router.refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Une erreur est survenue.')
      }
    })
  }

  const handleGenerateTracfin = () => {
    setError(null)
    startTransition(async () => {
      try {
        const result = await generateTracfinReport(item.transfer_id)
        setDownloadUrl(result.download_url)
        onUpdated({ tracfin_report_generated: true })
        router.refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Une erreur est survenue.')
      }
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 p-6 relative max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
          aria-label="Fermer"
        >
          <X size={20} />
        </button>

        <h2 className="text-18 font-bold text-gray-900 mb-1">Cas HARD_BLOCK</h2>
        <p className="text-12 text-gray-500 mb-4 font-mono">{item.transfer_id}</p>

        <div className="rounded-lg border border-red-200 bg-red-50 p-3 mb-5 space-y-1">
          <p className="text-13 font-medium text-red-800">
            Match sanctions confirmé — transfert déjà bloqué
          </p>
          <p className="text-12 text-red-700">
            Entrée : {item.ofac_matched_entry ?? '—'} · Similarité :{' '}
            {item.ofac_similarity !== null ? `${Math.round(item.ofac_similarity * 100)}%` : '—'}
            {item.ofac_list ? ` · Liste : ${item.ofac_list}` : ''}
          </p>
        </div>

        {error && (
          <p className="text-13 text-red-600 mb-4 flex items-center gap-1">
            <AlertCircle size={14} /> {error}
          </p>
        )}

        {/* Action 1 — documenter */}
        <div className="mb-5 pb-5 border-b border-gray-100">
          <label className="block text-14 font-medium text-gray-700 mb-1">
            Documenter le cas
            <span className="block text-11 text-gray-400 font-normal">
              Note interne, horodatée, avec votre identité — n&apos;est jamais une décision.
            </span>
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            placeholder="Constat, contexte, actions déjà menées..."
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-14 text-gray-900 resize-none mb-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleDocument}
            disabled={isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800 text-white text-13 font-semibold hover:bg-gray-900 disabled:opacity-50 transition"
          >
            <FileText size={14} />
            {item.is_documented ? 'Ajouter une note' : 'Documenter'}
          </button>
        </div>

        {/* Action 2 — geler le compte */}
        <div className="mb-5 pb-5 border-b border-gray-100">
          <p className="text-14 font-medium text-gray-700 mb-1">Geler le compte de l&apos;émetteur</p>
          <p className="text-11 text-gray-400 mb-2">
            Bloque toute nouvelle initiation de transfert. Journalisé on-chain immédiatement.
          </p>
          <button
            onClick={handleFreeze}
            disabled={isPending || item.account_frozen}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 text-white text-13 font-semibold hover:bg-red-700 disabled:opacity-50 transition"
          >
            <Lock size={14} />
            {item.account_frozen ? 'Compte déjà gelé' : 'Geler le compte'}
          </button>
        </div>

        {/* Action 3 — générer la déclaration TRACFIN */}
        <div>
          <p className="text-14 font-medium text-gray-700 mb-1">Déclaration TRACFIN</p>
          <p className="text-11 text-gray-400 mb-2">
            PDF structurel à visée académique — sans valeur légale, jamais transmis.
          </p>
          <button
            onClick={handleGenerateTracfin}
            disabled={isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-orange-600 text-white text-13 font-semibold hover:bg-orange-700 disabled:opacity-50 transition"
          >
            <FileWarning size={14} />
            {item.tracfin_report_generated ? 'Régénérer le rapport' : 'Générer le rapport'}
          </button>
          {downloadUrl && (
            <a
              href={downloadUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 flex items-center gap-1 text-13 font-medium text-blue-600 hover:underline"
            >
              <ExternalLink size={14} />
              Télécharger le PDF
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
