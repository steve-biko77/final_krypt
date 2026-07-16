import { Skeleton } from '@/components/ui/skeleton'

/** Fallback <Suspense> de RecentTransfersList — même silhouette qu'une JourneyCard. */
export default function RecentTransfersSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-busy="true" aria-label="Chargement des transferts récents">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-3 sm:p-4">
          <Skeleton className="size-11 rounded-full shrink-0" />
          <div className="min-w-0 flex-1">
            <Skeleton className="h-4 w-32 mb-2" />
            <Skeleton className="h-3 w-20" />
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1.5">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-14 rounded-full" />
          </div>
        </div>
      ))}
    </div>
  )
}
