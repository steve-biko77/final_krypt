'use client'

import { useEffect, useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { AlertCircle, ExternalLink, FileWarning } from 'lucide-react'
import { toast } from 'sonner'
import {
  generateTracfinReport,
  getTracfinReportDownloadUrl,
} from '@/lib/actions/admin-aml.actions'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

interface AMLHardBlockTracfinDialogProps {
  transferId: string
  isGenerated: boolean
  onGenerated: () => void
}

export default function AMLHardBlockTracfinDialog({
  transferId,
  isGenerated,
  onGenerated,
}: AMLHardBlockTracfinDialogProps) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadingExisting, setLoadingExisting] = useState(false)
  const [isPending, startTransition] = useTransition()

  // À l'ouverture, si un rapport existe déjà, on récupère un lien signé FRAIS
  // via le GET dédié (KRYP-31 partie 2/3) plutôt que d'en régénérer un — le
  // lien présigné MinIO expire au bout d'une heure, jamais mis en cache.
  useEffect(() => {
    if (!open || !isGenerated) return
    setError(null)
    setLoadingExisting(true)
    getTracfinReportDownloadUrl(transferId)
      .then((res) => setDownloadUrl(res.download_url))
      .catch((e) => setError(e instanceof Error ? e.message : 'Chargement impossible.'))
      .finally(() => setLoadingExisting(false))
  }, [open, isGenerated, transferId])

  const handleGenerate = () => {
    setError(null)
    startTransition(async () => {
      try {
        const result = await generateTracfinReport(transferId)
        setDownloadUrl(result.download_url)
        router.refresh()
        toast.success('Déclaration TRACFIN générée')
        onGenerated()
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Une erreur est survenue.'
        setError(message)
        toast.error('Échec de la génération', { description: message })
      }
    })
  }

  const busy = isPending || loadingExisting

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) setDownloadUrl(null)
      }}
    >
      <DialogTrigger asChild>
        <Button type="button" variant="secondary" size="sm">
          <FileWarning size={14} />
          {isGenerated ? 'Voir le rapport TRACFIN' : 'Générer le rapport TRACFIN'}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Déclaration TRACFIN</DialogTitle>
          <DialogDescription>
            PDF structurel à visée académique — sans valeur légale, jamais transmis à un tiers.
          </DialogDescription>
        </DialogHeader>

        {busy && (
          <div className="space-y-2" aria-busy="true" aria-label="Génération du rapport en cours">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <p className="text-12 text-gray-400">
              {isPending ? 'Génération du PDF en cours…' : 'Récupération du rapport existant…'}
            </p>
          </div>
        )}

        {error && (
          <p className="text-13 text-red-600 flex items-center gap-1">
            <AlertCircle size={14} /> {error}
          </p>
        )}

        {!busy && downloadUrl && (
          <a
            href={downloadUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-14 font-medium text-blue-600 hover:underline"
          >
            <ExternalLink size={14} />
            Télécharger le PDF
          </a>
        )}

        <DialogFooter>
          {!isGenerated && (
            <Button type="button" onClick={handleGenerate} disabled={busy}>
              {isPending ? 'Génération…' : 'Générer le rapport'}
            </Button>
          )}
          {isGenerated && (
            <Button type="button" variant="outline" onClick={handleGenerate} disabled={busy}>
              {isPending ? 'Génération…' : 'Régénérer'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
