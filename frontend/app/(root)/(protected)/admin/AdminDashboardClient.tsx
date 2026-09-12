'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { AlertCircle, ArrowRight, ArrowUpCircle, ShieldAlert } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { getAdminStats, type AdminStats } from '@/lib/actions/admin-aml.actions'

type StatusVariant = 'success' | 'active' | 'secondary' | 'warning' | 'destructive'

// Mêmes libellés que TransactionStatus.choices côté backend
// (contexts/transfer/models.py) — vue d'ensemble complète, pas seulement les
// statuts déjà affichés dans la console AML (pending/escalated/hard-block).
const STATUS_LABELS: Record<string, string> = {
  DRAFT: 'Brouillon',
  PENDING_AML: 'En attente scoring AML',
  AML_BLOCKED: 'Bloqué par AML',
  AML_PENDING_REVIEW: 'Révision AML requise',
  PROCESSING: 'Paiement en cours',
  ESCROWED: 'Fonds sécurisés (escrow)',
  ESCROW_FAILED: 'Échec verrouillage escrow',
  DELIVERED: 'Livré',
  PAYMENT_FAILED: 'Paiement échoué',
  PAYOUT_FAILED: 'Échec payout mobile money',
  CANCELLED: 'Annulé',
  AWAITING_DOCS: 'Documents complémentaires requis',
  ESCALATED: 'Escaladé (revue niveau 2)',
}

const STATUS_BADGE_VARIANT: Record<string, StatusVariant> = {
  DRAFT: 'secondary',
  PENDING_AML: 'secondary',
  AML_BLOCKED: 'destructive',
  AML_PENDING_REVIEW: 'warning',
  PROCESSING: 'active',
  ESCROWED: 'active',
  ESCROW_FAILED: 'destructive',
  DELIVERED: 'success',
  PAYMENT_FAILED: 'destructive',
  PAYOUT_FAILED: 'destructive',
  CANCELLED: 'secondary',
  AWAITING_DOCS: 'warning',
  ESCALATED: 'warning',
}

function formatEUR(value: string): string {
  const n = parseFloat(value)
  if (isNaN(n)) return value
  return n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function StatsLoadingSkeleton() {
  return (
    <div className="flex flex-col gap-8" aria-busy="true" aria-label="Chargement du tableau de bord">
      <div>
        <Skeleton className="h-8 w-64 mb-2" />
        <Skeleton className="h-4 w-48" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[0, 1, 2, 3].map((i) => (
          <Card key={i}>
            <CardContent className="px-4 flex flex-col gap-2">
              <Skeleton className="h-7 w-16" />
              <Skeleton className="h-3 w-20" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Skeleton className="h-32 w-full rounded-xl" />
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-28 w-full rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-36 w-full rounded-xl" />
    </div>
  )
}

export default function AdminDashboardClient() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getAdminStats()
      .then(setStats)
      .catch((e) => setError(e instanceof Error ? e.message : 'Chargement impossible.'))
  }, [])

  if (error) {
    return (
      <div className="flex items-start gap-2 p-4 rounded-xl bg-red-50 border border-red-200 max-w-xl">
        <AlertCircle size={18} className="text-red-500 mt-0.5 shrink-0" aria-hidden="true" />
        <p className="text-14 text-red-700">{error}</p>
      </div>
    )
  }

  if (!stats) {
    return <StatsLoadingSkeleton />
  }

  const totalTransfers = Object.values(stats.transactions_by_status).reduce((a, b) => a + b, 0)
  const statusEntries = Object.entries(stats.transactions_by_status)
    .filter(([, count]) => count > 0)
    .sort(([, a], [, b]) => b - a)
  const { today_decisions } = stats

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-24 font-bold text-gray-900">Tableau de bord admin</h1>
        <p className="text-14 text-gray-500 mt-1">Vue d&apos;ensemble de la plateforme</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card>
          <CardContent className="px-4 flex flex-col gap-1">
            <p className="text-24 font-bold text-gray-900">{stats.total_users}</p>
            <p className="text-12 text-gray-500">Clients</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="px-4 flex flex-col gap-1">
            <p className="text-24 font-bold text-gray-900">{stats.total_kyc_verified}</p>
            <p className="text-12 text-gray-500">KYC vérifiés</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="px-4 flex flex-col gap-1">
            <p className="text-24 font-bold text-gray-900">{totalTransfers}</p>
            <p className="text-12 text-gray-500">Transferts (total)</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="px-4 flex flex-col gap-1">
            <p className="font-mono text-24 font-bold text-gray-900">
              {formatEUR(stats.total_volume_eur)} €
            </p>
            <p className="text-12 text-gray-500">Volume livré</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-16">Répartition par statut</CardTitle>
          <CardDescription>
            Tous les transferts de la plateforme, statut le plus fréquent en premier
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {statusEntries.length === 0 ? (
            <p className="text-14 text-gray-400">Aucun transfert enregistré.</p>
          ) : (
            statusEntries.map(([statusKey, count]) => (
              <Badge
                key={statusKey}
                variant={STATUS_BADGE_VARIANT[statusKey] ?? 'secondary'}
                className="text-13 px-3 py-1"
              >
                {STATUS_LABELS[statusKey] ?? statusKey} · {count}
              </Badge>
            ))
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Link href="/admin/aml">
          <Card interactive className="h-full">
            <CardHeader>
              <CardTitle className="text-16 flex items-center gap-2">
                <ShieldAlert size={18} className="text-orange-500" aria-hidden="true" />
                Dossiers en revue
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-24 font-bold text-gray-900">{stats.pending_review_count}</p>
              <p className="text-13 text-gray-500 mt-1">En attente de premier niveau</p>
            </CardContent>
          </Card>
        </Link>
        <Link href="/admin/aml/escalated">
          <Card interactive className="h-full">
            <CardHeader>
              <CardTitle className="text-16 flex items-center gap-2">
                <ArrowUpCircle size={18} className="text-amber-500" aria-hidden="true" />
                Dossiers escaladés
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-24 font-bold text-gray-900">{stats.escalated_count}</p>
              <p className="text-13 text-gray-500 mt-1">Revue de second niveau</p>
            </CardContent>
          </Card>
        </Link>
        <Link href="/admin/aml/hard-block">
          <Card interactive className="h-full">
            <CardHeader>
              <CardTitle className="text-16 flex items-center gap-2">
                <AlertCircle size={18} className="text-red-500" aria-hidden="true" />
                Alertes HARD_BLOCK
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-24 font-bold text-gray-900">{stats.hard_block_count}</p>
              <p className="text-13 text-gray-500 mt-1">Match sanctions confirmé</p>
            </CardContent>
          </Card>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <CardTitle className="text-16">Décisions du jour</CardTitle>
              <CardDescription>
                {today_decisions.total_decisions} décision
                {today_decisions.total_decisions !== 1 ? 's' : ''} au{' '}
                {new Date(today_decisions.date).toLocaleDateString('fr-FR')}
              </CardDescription>
            </div>
            <Link
              href="/admin/aml/daily-report"
              className="flex items-center gap-1 text-13 font-medium text-blue-600 hover:underline"
            >
              Rapport complet <ArrowRight size={14} />
            </Link>
          </div>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Badge variant="success">Approuvés · {today_decisions.counts.approve}</Badge>
          <Badge variant="destructive">Rejetés · {today_decisions.counts.reject}</Badge>
          <Badge variant="warning">Escaladés · {today_decisions.counts.escalate}</Badge>
          <Badge variant="secondary">
            HARD_BLOCK documentés · {today_decisions.counts.hard_block_documented}
          </Badge>
          <Badge variant="secondary">
            Comptes gelés · {today_decisions.counts.hard_block_frozen}
          </Badge>
          <Badge variant="secondary">
            Déclarations TRACFIN · {today_decisions.counts.hard_block_tracfin_generated}
          </Badge>
        </CardContent>
      </Card>
    </div>
  )
}
