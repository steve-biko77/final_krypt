import TransferStepper from './TransferStepper'

export default function TransferPage() {
  return (
    <section className="flex flex-col gap-8 p-4 sm:p-8">
      <div>
        <h1 className="font-heading tracking-heading text-24 sm:text-30 font-bold text-gray-900">
          Envoyer de l&apos;argent
        </h1>
        <p className="text-16 md:text-14 text-gray-500 mt-1">
          Transfert France → Cameroun via Mobile Money
        </p>
      </div>
      <TransferStepper />
    </section>
  )
}
