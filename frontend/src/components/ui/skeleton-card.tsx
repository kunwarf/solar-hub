import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

interface SkeletonCardProps {
  className?: string;
}

export function StatCardSkeleton({ className }: SkeletonCardProps) {
  return (
    <div className={cn("glass-card p-4", className)}>
      <div className="flex items-start gap-3">
        <Skeleton className="w-10 h-10 rounded-xl" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-6 w-16" />
        </div>
      </div>
    </div>
  );
}

export function ChartSkeleton({ className }: SkeletonCardProps) {
  return (
    <div className={cn("glass-card p-6", className)}>
      <Skeleton className="h-5 w-32 mb-6" />
      <div className="space-y-3">
        <div className="flex items-end gap-2 h-[300px]">
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton 
              key={i} 
              className="flex-1 rounded-t-sm" 
              style={{ height: `${Math.random() * 60 + 20}%` }} 
            />
          ))}
        </div>
        <div className="flex justify-between">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-3 w-8" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function EnergyFlowSkeleton({ className }: SkeletonCardProps) {
  return (
    <div className={cn("glass-card p-6", className)}>
      <div className="flex items-center justify-between mb-4">
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-4 w-12" />
      </div>
      <div className="flex flex-col items-center justify-center h-[400px] space-y-8">
        {/* Solar node */}
        <Skeleton className="w-16 h-16 rounded-full" />
        
        {/* Center hub */}
        <Skeleton className="w-12 h-12 rounded-full" />
        
        {/* Bottom nodes */}
        <div className="flex items-center justify-between w-full max-w-[400px]">
          <Skeleton className="w-16 h-16 rounded-full" />
          <Skeleton className="w-16 h-16 rounded-full" />
          <Skeleton className="w-16 h-16 rounded-full" />
        </div>
      </div>
    </div>
  );
}

export function DeviceCardSkeleton({ className }: SkeletonCardProps) {
  return (
    <div className={cn("rounded-lg border border-border/50 bg-card/50 p-4", className)}>
      <div className="flex items-center gap-4 mb-3">
        <Skeleton className="w-10 h-10 rounded-lg" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-3 w-16" />
        </div>
        <Skeleton className="w-2.5 h-2.5 rounded-full" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-12 rounded-md" />
        ))}
      </div>
    </div>
  );
}

export function BillingSummarySkeleton({ className }: SkeletonCardProps) {
  return (
    <div className={cn("glass-card p-6", className)}>
      <div className="flex items-center justify-between mb-4">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-8 w-24 rounded-md" />
      </div>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-6 w-16" />
        </div>
        <Skeleton className="h-2 w-full rounded-full" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-16 rounded-md" />
          <Skeleton className="h-16 rounded-md" />
        </div>
      </div>
    </div>
  );
}
