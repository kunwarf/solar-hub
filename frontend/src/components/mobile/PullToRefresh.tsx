import { useState, useCallback, useRef, useEffect } from 'react';
import { RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { motion, useMotionValue, useTransform, PanInfo } from 'framer-motion';

interface PullToRefreshProps {
  onRefresh: () => Promise<void>;
  children: React.ReactNode;
  className?: string;
  disabled?: boolean;
}

const PULL_THRESHOLD = 80;
const MAX_PULL = 120;

export const PullToRefresh = ({ 
  onRefresh, 
  children, 
  className,
  disabled = false 
}: PullToRefreshProps) => {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isPulling, setIsPulling] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const y = useMotionValue(0);
  const pullProgress = useTransform(y, [0, PULL_THRESHOLD], [0, 1]);
  const rotation = useTransform(y, [0, PULL_THRESHOLD], [0, 180]);

  const handlePan = useCallback((event: TouchEvent | MouseEvent, info: PanInfo) => {
    if (disabled || isRefreshing) return;
    
    // Only allow pull when at top of scroll
    if (containerRef.current && containerRef.current.scrollTop > 0) return;
    
    if (info.delta.y > 0 || isPulling) {
      setIsPulling(true);
      const newY = Math.min(info.offset.y * 0.5, MAX_PULL);
      y.set(Math.max(0, newY));
    }
  }, [disabled, isRefreshing, isPulling, y]);

  const handlePanEnd = useCallback(async () => {
    if (disabled || isRefreshing) return;
    
    if (y.get() >= PULL_THRESHOLD) {
      setIsRefreshing(true);
      
      // Trigger haptic feedback if supported
      if ('vibrate' in navigator) {
        navigator.vibrate(10);
      }
      
      try {
        await onRefresh();
      } finally {
        setIsRefreshing(false);
      }
    }
    
    y.set(0);
    setIsPulling(false);
  }, [disabled, isRefreshing, onRefresh, y]);

  return (
    <div ref={containerRef} className={cn("relative overflow-hidden", className)}>
      {/* Pull indicator */}
      <motion.div
        className="absolute left-0 right-0 flex items-center justify-center z-10 pointer-events-none"
        style={{ 
          top: useTransform(y, (val) => val - 40),
          opacity: useTransform(y, [0, 40, PULL_THRESHOLD], [0, 0.5, 1])
        }}
      >
        <motion.div
          className={cn(
            "w-10 h-10 rounded-full bg-card border flex items-center justify-center shadow-lg",
            isRefreshing && "bg-primary/10"
          )}
        >
          <motion.div
            style={{ rotate: isRefreshing ? undefined : rotation }}
            animate={isRefreshing ? { rotate: 360 } : undefined}
            transition={isRefreshing ? { duration: 1, repeat: Infinity, ease: "linear" } : undefined}
          >
            <RefreshCw className={cn(
              "w-5 h-5",
              isRefreshing ? "text-primary" : "text-muted-foreground"
            )} />
          </motion.div>
        </motion.div>
      </motion.div>

      {/* Content */}
      <motion.div
        style={{ y }}
        onPan={handlePan as any}
        onPanEnd={handlePanEnd}
        className="touch-pan-y"
      >
        {children}
      </motion.div>
    </div>
  );
};

// Simple hook for manual refresh control
export const usePullToRefresh = () => {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refresh = useCallback(async (refreshFn: () => Promise<void>) => {
    setIsRefreshing(true);
    
    // Trigger haptic feedback if supported
    if ('vibrate' in navigator) {
      navigator.vibrate(10);
    }
    
    try {
      await refreshFn();
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  return { isRefreshing, refresh };
};
