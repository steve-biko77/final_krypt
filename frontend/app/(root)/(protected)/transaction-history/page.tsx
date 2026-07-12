import HeaderBox from '@/components/HeaderBox'

const TransactionHistory = async () => {
  return (
    <div className='transactions'>
      <div className='transactions-header'>
        <HeaderBox
          title='Historique des transferts'
          subtext='Consultez vos transferts passés'
        />
      </div>
      <div className='space-y-6 p-6'>
        <p className='text-16 text-gray-600'>
          L&apos;historique des transferts sera disponible prochainement.
        </p>
      </div>
    </div>
  )
}

export default TransactionHistory
