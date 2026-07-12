import HeaderBox from '@/components/HeaderBox'
import TransferStepper from './TransferStepper'

export default function TransferPage() {
  return (
    <section className="flex flex-col gap-8 p-8">
      <HeaderBox
        title="Envoyer de l&apos;argent"
        subtext="Transfert France → Cameroun via Mobile Money"
      />
      <TransferStepper />
    </section>
  )
}
