import HeaderBox from '@/components/HeaderBox'
import KYCUploadForm from '@/components/KYCUploadForm'
import { getKYCStatus } from '@/lib/actions/kyc.actions'
import type { KYCDocumentStatus } from '@/lib/actions/kyc.actions'
import { CheckCircle, Clock, XCircle, AlertCircle } from 'lucide-react'

const statusDisplay: Record<
  KYCDocumentStatus,
  {
    icon: typeof Clock
    color: string
    bg: string
    label: string
    description: string
    canUpload: boolean
  }
> = {
  SUBMITTED: {
    icon: Clock,
    color: 'text-yellow-500',
    bg: 'bg-yellow-50 border-yellow-200',
    label: 'Document soumis',
    description: "Votre document a été reçu et sera analysé prochainement.",
    canUpload: false,
  },
  ANALYZING: {
    icon: Clock,
    color: 'text-yellow-500',
    bg: 'bg-yellow-50 border-yellow-200',
    label: "Analyse en cours",
    description: "Votre document est en cours d'analyse automatique.",
    canUpload: false,
  },
  APPROVED: {
    icon: CheckCircle,
    color: 'text-green-500',
    bg: 'bg-green-50 border-green-200',
    label: 'Identité vérifiée',
    description: 'Votre KYC est validé. Vous pouvez effectuer des transferts.',
    canUpload: false,
  },
  APPROVED_MANUAL: {
    icon: CheckCircle,
    color: 'text-green-500',
    bg: 'bg-green-50 border-green-200',
    label: 'Identité vérifiée',
    description: 'Votre KYC a été validé manuellement. Vous pouvez effectuer des transferts.',
    canUpload: false,
  },
  PENDING_REVIEW: {
    icon: Clock,
    color: 'text-yellow-500',
    bg: 'bg-yellow-50 border-yellow-200',
    label: "Examen manuel en cours",
    description: "Votre document est examiné par notre équipe. Les transferts seront activés après validation.",
    canUpload: false,
  },
  COMPLEMENT_REQUESTED: {
    icon: AlertCircle,
    color: 'text-blue-500',
    bg: 'bg-blue-50 border-blue-200',
    label: 'Documents supplémentaires demandés',
    description: "Notre équipe a besoin d'informations complémentaires. Veuillez soumettre un nouveau document.",
    canUpload: true,
  },
  REJECTED: {
    icon: XCircle,
    color: 'text-red-500',
    bg: 'bg-red-50 border-red-200',
    label: 'Document rejeté',
    description: 'Votre document a été rejeté. Veuillez en soumettre un nouveau.',
    canUpload: true,
  },
}

const KYCPage = async () => {
  const { status, document } = await getKYCStatus()
  const config = status ? statusDisplay[status] : null
  const Icon = config?.icon

  const canUpload = !status || (config?.canUpload ?? false)

  return (
    <section className="flex flex-col gap-8 p-8 max-w-2xl">
      <HeaderBox
        title="Vérification d&apos;identité (KYC)"
        subtext="Soumettez un document officiel pour activer vos transferts"
      />

      {config && Icon && (
        <div className={`flex items-start gap-4 p-5 rounded-xl border ${config.bg}`}>
          <Icon size={24} className={`${config.color} shrink-0 mt-0.5`} />
          <div>
            <p className="text-16 font-semibold text-gray-900">{config.label}</p>
            <p className="text-14 text-gray-600 mt-1">{config.description}</p>
            {document && (
              <p className="text-12 text-gray-400 mt-2">
                Soumis le{' '}
                {document.submitted_at
                  ? new Date(document.submitted_at).toLocaleDateString('fr-FR')
                  : '—'}
                {' · '}
                Type : {document.document_type.replace('_', ' ')}
              </p>
            )}
          </div>
        </div>
      )}

      {canUpload && (
        <div className="flex flex-col gap-4">
          <div className="border-t border-gray-100 pt-6">
            <h2 className="text-18 font-semibold text-gray-900 mb-1">
              {status ? 'Soumettre un nouveau document' : 'Soumettre votre document'}
            </h2>
            <p className="text-14 text-gray-500 mb-6">
              Documents acceptés : carte nationale d&apos;identité, passeport, titre de séjour.
              Le document doit être lisible et en cours de validité.
            </p>
            <KYCUploadForm />
          </div>
        </div>
      )}

      {!status && !config && (
        <div className="flex flex-col gap-4">
          <div className="border-t border-gray-100 pt-6">
            <h2 className="text-18 font-semibold text-gray-900 mb-1">
              Soumettre votre document d&apos;identité
            </h2>
            <p className="text-14 text-gray-500 mb-6">
              Documents acceptés : carte nationale d&apos;identité, passeport, titre de séjour.
              Le document doit être lisible et en cours de validité.
            </p>
            <KYCUploadForm />
          </div>
        </div>
      )}
    </section>
  )
}

export default KYCPage
