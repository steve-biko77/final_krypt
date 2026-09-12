'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { AlertCircle, Lock } from 'lucide-react'
import { toast } from 'sonner'
import { freezeAccount } from '@/lib/actions/admin-aml.actions'
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

interface AMLHardBlockFreezeDialogProps {
  transferId: string
  senderLabel: string
  isFrozen: boolean
  onFrozen: () => void
}

// Refonte frontend (partie 4b/4) — action impactante pour l'utilisateur
// concerné : confirmation OBLIGATOIRE via Dialog avant tout appel API,
// contrairement à "documenter" qui n'a pas d'effet sur le compte.
export default function AMLHardBlockFreezeDialog({
  transferId,
  senderLabel,
  isFrozen,
  onFrozen,
}: AMLHardBlockFreezeDialogProps) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()

  const handleFreeze = () => {
    setError(null)
    startTransition(async () => {
      try {
        await freezeAccount(transferId)
        router.refresh()
        toast.success('Compte gelé')
        setOpen(false)
        onFrozen()
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Une erreur est survenue.'
        setError(message)
        toast.error('Échec du gel du compte', { description: message })
      }
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="destructive" size="sm" disabled={isFrozen}>
          <Lock size={14} />
          {isFrozen ? 'Compte déjà gelé' : 'Geler le compte'}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Geler le compte de l&apos;émetteur ?</DialogTitle>
          <DialogDescription>
            <strong className="text-gray-900">{senderLabel}</strong> ne pourra plus initier
            aucun nouveau transfert tant que le compte reste gelé. Cette action est journalisée
            on-chain immédiatement.
          </DialogDescription>
        </DialogHeader>
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
          <Button type="button" variant="destructive" onClick={handleFreeze} disabled={isPending}>
            {isPending ? 'Gel en cours…' : 'Confirmer le gel du compte'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
