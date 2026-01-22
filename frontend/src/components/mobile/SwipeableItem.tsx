import { useState, useCallback, useRef } from 'react';
import { motion, PanInfo, useMotionValue, useTransform, AnimatePresence } from 'framer-motion';
import { Settings, Activity, X, Check } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SwipeableItemProps {
  children: React.ReactNode;
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
  leftAction?: {
    icon: React.ReactNode;
    label: string;
    color: string;
    bgColor: string;
  };
  rightAction?: {
    icon: React.ReactNode;
    label: string;
    color: string;
    bgColor: string;
  };
  className?: string;
  disabled?: boolean;
}

const SWIPE_THRESHOLD = 80;
const MAX_SWIPE = 120;

export const SwipeableItem = ({
  children,
  onSwipeLeft,
  onSwipeRight,
  leftAction = {
    icon: <Activity className="w-5 h-5" />,
    label: "Telemetry",
    color: "text-primary",
    bgColor: "bg-primary/20",
  },
  rightAction = {
    icon: <Settings className="w-5 h-5" />,
    label: "Settings",
    color: "text-muted-foreground",
    bgColor: "bg-muted",
  },
  className,
  disabled = false,
}: SwipeableItemProps) => {
  const x = useMotionValue(0);
  const [isDragging, setIsDragging] = useState(false);
  
  const leftOpacity = useTransform(x, [-MAX_SWIPE, -SWIPE_THRESHOLD/2, 0], [1, 0.5, 0]);
  const rightOpacity = useTransform(x, [0, SWIPE_THRESHOLD/2, MAX_SWIPE], [0, 0.5, 1]);
  
  const leftScale = useTransform(x, [-MAX_SWIPE, -SWIPE_THRESHOLD, 0], [1, 0.8, 0.5]);
  const rightScale = useTransform(x, [0, SWIPE_THRESHOLD, MAX_SWIPE], [0.5, 0.8, 1]);

  const handleDrag = useCallback((event: TouchEvent | MouseEvent, info: PanInfo) => {
    if (disabled) return;
    setIsDragging(true);
  }, [disabled]);

  const handleDragEnd = useCallback((event: TouchEvent | MouseEvent, info: PanInfo) => {
    if (disabled) return;
    
    const threshold = SWIPE_THRESHOLD;
    
    if (info.offset.x < -threshold && onSwipeLeft) {
      // Trigger haptic feedback
      if ('vibrate' in navigator) {
        navigator.vibrate(10);
      }
      onSwipeLeft();
    } else if (info.offset.x > threshold && onSwipeRight) {
      // Trigger haptic feedback
      if ('vibrate' in navigator) {
        navigator.vibrate(10);
      }
      onSwipeRight();
    }
    
    setIsDragging(false);
  }, [disabled, onSwipeLeft, onSwipeRight]);

  return (
    <div className={cn("relative overflow-hidden rounded-lg", className)}>
      {/* Left action (revealed on swipe right) */}
      {onSwipeRight && (
        <motion.div
          className={cn(
            "absolute inset-y-0 left-0 flex items-center justify-start pl-4 w-24",
            rightAction.bgColor
          )}
          style={{ opacity: rightOpacity }}
        >
          <motion.div 
            className={cn("flex flex-col items-center gap-1", rightAction.color)}
            style={{ scale: rightScale }}
          >
            {rightAction.icon}
            <span className="text-xs font-medium">{rightAction.label}</span>
          </motion.div>
        </motion.div>
      )}

      {/* Right action (revealed on swipe left) */}
      {onSwipeLeft && (
        <motion.div
          className={cn(
            "absolute inset-y-0 right-0 flex items-center justify-end pr-4 w-24",
            leftAction.bgColor
          )}
          style={{ opacity: leftOpacity }}
        >
          <motion.div 
            className={cn("flex flex-col items-center gap-1", leftAction.color)}
            style={{ scale: leftScale }}
          >
            {leftAction.icon}
            <span className="text-xs font-medium">{leftAction.label}</span>
          </motion.div>
        </motion.div>
      )}

      {/* Main content */}
      <motion.div
        drag={disabled ? false : "x"}
        dragConstraints={{ left: onSwipeLeft ? -MAX_SWIPE : 0, right: onSwipeRight ? MAX_SWIPE : 0 }}
        dragElastic={0.1}
        style={{ x }}
        onDrag={handleDrag as any}
        onDragEnd={handleDragEnd as any}
        className={cn(
          "relative bg-card z-10",
          isDragging && "cursor-grabbing"
        )}
      >
        {children}
      </motion.div>
    </div>
  );
};

// Swipeable alert item with dismiss action
interface SwipeableAlertProps {
  children: React.ReactNode;
  onDismiss: () => void;
  className?: string;
}

export const SwipeableAlert = ({ children, onDismiss, className }: SwipeableAlertProps) => {
  const [isDismissed, setIsDismissed] = useState(false);
  
  const handleDismiss = () => {
    setIsDismissed(true);
    if ('vibrate' in navigator) {
      navigator.vibrate(10);
    }
    setTimeout(onDismiss, 200);
  };

  return (
    <AnimatePresence>
      {!isDismissed && (
        <motion.div
          initial={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0, marginBottom: 0 }}
          transition={{ duration: 0.2 }}
        >
          <SwipeableItem
            onSwipeRight={handleDismiss}
            rightAction={{
              icon: <Check className="w-5 h-5" />,
              label: "Dismiss",
              color: "text-success",
              bgColor: "bg-success/20",
            }}
            className={className}
          >
            {children}
          </SwipeableItem>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
