'use client'

import { useTransition, useState, useRef } from 'react'
import { submitKYC, type KYCDocument } from '@/lib/actions/kyc.actions'
import { Button } from '@/components/ui/button'
import { Loader2, UploadCloud, CheckCircle } from 'lucide-react'

interface KYCUploadFormProps {
  onSuccess?: (doc: KYCDocument) => void
}

const DOCUMENT_TYPES = [
  { value: 'ID_CARD', label: "Carte nationale d'identité" },
  { value: 'PASSPORT', label: 'Passeport' },
  { value: 'RESIDENCE_PERMIT', label: 'Titre de séjour' },
]

const KYCUploadForm = ({ onSuccess }: KYCUploadFormProps) => {
  const [isPending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [fileName, setFileName] = useState<string | null>(null)
  const formRef = useRef<HTMLFormElement>(null)

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setError(null)

    const formData = new FormData(e.currentTarget)

    startTransition(async () => {
      try {
        const doc = await submitKYC(formData)
        setSuccess(true)
        formRef.current?.reset()
        setFileName(null)
        onSuccess?.(doc)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Une erreur est survenue')
      }
    })
  }

  if (success) {
    return (
      <div className="flex flex-col items-center gap-4 p-8 text-center">
        <CheckCircle size={48} className="text-green-500" />
        <h3 className="text-18 font-semibold text-gray-900">Document soumis avec succès</h3>
        <p className="text-14 text-gray-600">
          Votre document est en cours d&apos;examen. Vous serez notifié dès que la vérification sera terminée.
        </p>
      </div>
    )
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <label className="text-14 font-medium text-gray-700">
          Type de document
        </label>
        <select
          name="document_type"
          required
          className="input-class h-10 px-3 rounded-md border border-gray-300 bg-white text-14 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Sélectionnez un type</option>
          {DOCUMENT_TYPES.map((dt) => (
            <option key={dt.value} value={dt.value}>
              {dt.label}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-14 font-medium text-gray-700">
          Document (JPG, PNG ou PDF, max 5 Mo)
        </label>
        <label className="flex flex-col items-center justify-center gap-3 p-8 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors">
          <UploadCloud size={32} className="text-gray-400" />
          {fileName ? (
            <span className="text-14 font-medium text-blue-600">{fileName}</span>
          ) : (
            <span className="text-14 text-gray-500">
              Cliquez ou glissez-déposez votre fichier ici
            </span>
          )}
          <input
            type="file"
            name="file"
            accept=".jpg,.jpeg,.png,.pdf"
            required
            className="hidden"
            onChange={(e) => setFileName(e.target.files?.[0]?.name ?? null)}
          />
        </label>
      </div>

      {error && (
        <p className="text-14 font-medium text-red-500 bg-red-50 p-3 rounded-md">
          {error}
        </p>
      )}

      <Button
        type="submit"
        disabled={isPending}
        className="form-btn"
      >
        {isPending ? (
          <>
            <Loader2 size={18} className="animate-spin mr-2" />
            Envoi en cours...
          </>
        ) : (
          'Soumettre le document'
        )}
      </Button>
    </form>
  )
}

export default KYCUploadForm
