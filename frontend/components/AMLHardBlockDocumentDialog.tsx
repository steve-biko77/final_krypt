'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { AlertCircle, FileText } from 'lucide-react'
import { toast } from 'sonner'
import { documentHardBlockCase } from '@/lib/actions/admin-aml.actions'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

interface AMLHardBlockDocumentDialogProps {
  transferId: string
  isDocumented: boolean
  onDocumented: () => void
}

export default function AMLHardBlockDocumentDialog({
  transferId,
  isDocumented,
  onDocumented,
}: AMLHardBlockDocumentDialogProps) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()

  const handleSave = () => {
    if (!note.trim()) {
      setError('Une note est requise pour documenter ce cas.')
      return
    }
    setError(null)
    startTransition(async () => {
      try {
        await documentHardBlockCase(transferId, note)
        router.refresh()
        toast.success('Dossier documenté')
        setNote('')
        setOpen(false)
        onDocumented()
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Une erreur est survenue.'
        setError(message)
        toast.error('Échec de la documentation', { description: message })
      }
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm">
          <FileText size={14} />
          {isDocumented ? 'Ajouter une note' : 'Documenter'}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Documenter le dossier</DialogTitle>
          <DialogDescription>
            Note interne, horodatée, avec votre identité — n&apos;est jamais une décision.
          </DialogDescription>
        </DialogHeader>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={4}
          placeholder="Constat, contexte, actions déjà menées..."
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-14 text-gray-900 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {error && (
          <p className="text-13 text-red-600 flex items-center gap-1">
            <AlertCircle size={14} /> {error}
          </p>
        )}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => setOpen(false)}
            disabled={isPending}
          >
            Annuler
          </Button>
          <Button type="button" onClick={handleSave} disabled={isPending}>
            {isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
