import Link from 'next/link'
import { AlertCircle, CheckCircle, Clock, XCircle } from 'lucide-react'
import type { KYCDocumentStatus } from '@/lib/actions/kyc.actions'

interface KYCBannerProps {
  kycStatus: KYCDocumentStatus | null
}

const statusConfig = {
  PENDING: {
    icon: Clock,
    bg: 'bg-yellow-50 border-yellow-200',
    iconColor: 'text-yellow-500',
    title: 'Vérification en cours',
    text: "Votre document est en cours d’examen. Les transferts seront activés après validation.",
    showLink: false,
  },
  APPROVED: {
    icon: CheckCircle,
    bg: 'bg-green-50 border-green-200',
    iconColor: 'text-green-500',
    title: 'Identité vérifiée',
    text: 'Votre KYC est validé. Vous pouvez effectuer des transferts.',
    showLink: false,
  },
  REJECTED: {
    icon: XCircle,
    bg: 'bg-red-50 border-red-200',
    iconColor: 'text-red-500',
    title: 'Document rejeté',
    text: 'Votre document a été rejeté. Veuillez en soumettre un nouveau.',
    showLink: true,
  },
} as const

const KYCBanner = ({ kycStatus }: KYCBannerProps) => {
  if (kycStatus === 'APPROVED') return null

  const config = kycStatus ? statusConfig[kycStatus] : null
  const Icon = config?.icon ?? AlertCircle

  if (!config) {
    return (
      <div className="flex items-start gap-3 p-4 rounded-lg border bg-blue-50 border-blue-200 mb-6">
        <AlertCircle size={20} className="text-blue-500 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-14 font-semibold text-blue-900">
            Vérification d&apos;identité requise
          </p>
          <p className="text-12 text-blue-700 mt-0.5">
            Soumettez un document d&apos;identité pour activer vos transferts France → Cameroun.
          </p>
        </div>
        <Link
          href="/kyc"
          className="text-14 font-semibold text-blue-700 underline whitespace-nowrap"
        >
          Vérifier →
        </Link>
      </div>
    )
  }

  return (
    <div className={`flex items-start gap-3 p-4 rounded-lg border ${config.bg} mb-6`}>
      <Icon size={20} className={`${config.iconColor} mt-0.5 shrink-0`} />
      <div className="flex-1 min-w-0">
        <p className="text-14 font-semibold text-gray-900">{config.title}</p>
        <p className="text-12 text-gray-600 mt-0.5">{config.text}</p>
      </div>
      {config.showLink && (
        <Link href="/kyc" className="text-14 font-semibold text-red-700 underline whitespace-nowrap">
          Resoumettre →
        </Link>
      )}
    </div>
  )
}

export default KYCBanner
