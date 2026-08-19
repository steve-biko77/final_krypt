'use client'

import { useEffect, useState } from 'react'
import { Trash2, UserPlus } from 'lucide-react'
import { toast } from 'sonner'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { maskMobileNumber } from '@/lib/maskMobileNumber'
import {
  deleteBeneficiary,
  getSavedBeneficiaries,
  type SavedBeneficiary,
} from '@/lib/actions/beneficiaries.actions'

export interface BeneficiaryPickerProps {
  selectedId: string | null
  onSelect: (beneficiary: SavedBeneficiary) => void
  onNew: () => void
}

/**
 * Carnet de contacts — liste compacte des bénéficiaires enregistrés, en haut
 * de l'étape Destinataire du tunnel. Opt-in uniquement : cette liste ne fait
 * jamais rien de silencieux, elle ne fait que proposer une présélection que
 * l'utilisateur choisit explicitement. Rien n'est affiché si la liste est
 * vide (pas d'état "aucun bénéficiaire" intrusif) — le formulaire manuel
 * habituel suffit dans ce cas.
 */
export default function BeneficiaryPicker({ selectedId, onSelect, onNew }: BeneficiaryPickerProps) {
  const [beneficiaries, setBeneficiaries] = useState<SavedBeneficiary[] | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<SavedBeneficiary | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    let cancelled = false
    getSavedBeneficiaries().then((res) => {
      if (!cancelled) setBeneficiaries(res)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteBeneficiary(deleteTarget.id)
      setBeneficiaries((prev) => (prev ? prev.filter((b) => b.id !== deleteTarget.id) : prev))
      toast.success('Bénéficiaire supprimé')
      setDeleteTarget(null)
    } catch (e) {
      toast.error('Échec de la suppression', {
        description: e instanceof Error ? e.message : undefined,
      })
    } finally {
      setDeleting(false)
    }
  }

  if (beneficiaries === null) {
    return (
      <div
        className="flex flex-col gap-2"
        aria-busy="true"
        aria-label="Chargement des bénéficiaires enregistrés"
      >
        <Skeleton className="h-14 w-full rounded-lg" />
        <Skeleton className="h-14 w-full rounded-lg" />
      </div>
    )
  }

  if (beneficiaries.length === 0) return null

  return (
    <div className="flex flex-col gap-3" data-testid="beneficiary-picker">
      <div className="flex items-center justify-between">
        <p className="text-14 font-medium text-gray-700">Bénéficiaires enregistrés</p>
        {selectedId && (
          <button
            type="button"
            onClick={onNew}
            className="inline-flex items-center gap-1 text-13 font-semibold text-blue-600 hover:underline max-md:min-h-11"
          >
            <UserPlus size={14} aria-hidden="true" /> Nouveau bénéficiaire
          </button>
        )}
      </div>

      <div className="flex flex-col gap-2">
        {beneficiaries.map((b) => {
          const isSelected = b.id === selectedId
          return (
            <div
              key={b.id}
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 transition-colors ${
                isSelected ? 'border-blue-600 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <button
                type="button"
                onClick={() => onSelect(b)}
                aria-pressed={isSelected}
                className="flex min-h-11 min-w-0 flex-1 flex-col justify-center text-left"
              >
                <span className="truncate text-14 font-semibold text-gray-900">
                  {b.beneficiary_name}
                </span>
                <span className="truncate text-12 font-mono text-gray-500">
                  {maskMobileNumber(b.momo_number)}
                </span>
              </button>
              <button
                type="button"
                onClick={() => setDeleteTarget(b)}
                aria-label={`Supprimer ${b.beneficiary_name}`}
                className="flex size-11 shrink-0 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-red-50 hover:text-red-600"
              >
                <Trash2 size={16} aria-hidden="true" />
              </button>
            </div>
          )
        })}
      </div>

      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Supprimer ce bénéficiaire ?</DialogTitle>
            <DialogDescription>
              {deleteTarget?.beneficiary_name} sera retiré de vos bénéficiaires enregistrés.
              Cette action est irréversible.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setDeleteTarget(null)}
              disabled={deleting}
              className="max-md:h-11"
            >
              Annuler
            </Button>
            <Button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="bg-red-600 hover:bg-red-700 text-white max-md:h-11"
            >
              {deleting ? 'Suppression…' : 'Supprimer'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
