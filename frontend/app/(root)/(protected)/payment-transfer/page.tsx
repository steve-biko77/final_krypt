import HeaderBox from '@/components/HeaderBox'

const Transfer = async () => {
  return (
    <section className='payment-transfer'>
      <HeaderBox
        title='Transfert de fonds'
        subtext="Envoyez de l'argent vers le Cameroun via MTN MoMo ou Orange Money"
      />
      <div className='size-full pt-5 p-6'>
        <p className='text-16 text-gray-600'>
          Le module de transfert France → Cameroun sera disponible prochainement.
        </p>
      </div>
    </section>
  )
}

export default Transfer
