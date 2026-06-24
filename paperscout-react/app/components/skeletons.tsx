import { Skeleton } from "~/components/ui/skeleton"

export function SkeletonTable() {
  return (
    <div className="flex w-full flex-col gap-2">
      {Array.from({ length: 5 }).map((_, index) => (
        <div className="flex gap-4" key={index}>
          <Skeleton className="h-8 flex-1 rounded-lg" />
          <Skeleton className="h-8 flex-1 rounded-lg" />
          <Skeleton className="h-8 flex-1 rounded-lg" />
        </div>
      ))}
    </div>
  )
}

export function SkeletonList() {
  return (
    <div className="flex w-full flex-col flex-1 gap-4">
      {Array.from({ length: 15 }).map((_, index) => (
        <div className="flex gap-4" key={index}>
          <Skeleton className="h-25 flex-1 rounded-lg" />
        </div>
      ))}
    </div>
  )
}
