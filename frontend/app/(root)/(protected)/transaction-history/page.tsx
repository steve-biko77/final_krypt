import HeaderBox from '@/components/HeaderBox'
import RecentTransfersList from '@/components/RecentTransfersList'

// Correctif — cette page était un stub jamais câblé (aucun appel à
// GET /api/transfer/mine). Réutilise RecentTransfersList (Dashboard) plutôt
// que de recréer un rendu parallèle : mêmes JourneyCard / TransferRouteIndicator
// mini / badge de statut, même Skeleton, même message d'état vide.
//
// `limit=20` — plafond serveur (cf. AdminAML/find_by_sender, min(max(...),20))
// : pas de curseur de pagination côté API pour l'instant, donc pas de
// "Charger plus" qui ne pourrait rien charger de plus. Un `limit` généreux
// suffit pour ce projet (KRYP — historique des transferts).
const TransactionHistory = () => {
  return (
    <div className='transactions'>
      <div className='transactions-header'>
        <HeaderBox
          title='Historique des transferts'
          subtext='Consultez vos transferts passés'
        />
      </div>
      <div className='max-w-4xl'>
        <RecentTransfersList limit={20} />
      </div>
    </div>
  )
}

export default TransactionHistory
