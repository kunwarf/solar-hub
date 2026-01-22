import { RefreshCw, Phone, AlertOctagon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface MobileActionButtonProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  variant?: 'default' | 'destructive' | 'success' | 'warning';
  size?: 'default' | 'large';
  disabled?: boolean;
  loading?: boolean;
  className?: string;
}

const variantStyles = {
  default: 'bg-primary hover:bg-primary/90 text-primary-foreground',
  destructive: 'bg-destructive hover:bg-destructive/90 text-destructive-foreground',
  success: 'bg-success hover:bg-success/90 text-success-foreground',
  warning: 'bg-warning hover:bg-warning/90 text-warning-foreground',
};

// Trigger haptic feedback
const triggerHaptic = (pattern: number | number[] = 10) => {
  if ('vibrate' in navigator) {
    navigator.vibrate(pattern);
  }
};

export const MobileActionButton = ({
  icon,
  label,
  onClick,
  variant = 'default',
  size = 'default',
  disabled = false,
  loading = false,
  className,
}: MobileActionButtonProps) => {
  const handleClick = () => {
    if (disabled || loading) return;
    triggerHaptic();
    onClick();
  };

  return (
    <button
      onClick={handleClick}
      disabled={disabled || loading}
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-xl transition-all touch-manipulation",
        "active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed",
        size === 'large' ? 'p-6 min-h-[100px]' : 'p-4 min-h-[72px]',
        variantStyles[variant],
        className
      )}
    >
      <div className={cn(
        "transition-transform",
        loading && "animate-spin"
      )}>
        {loading ? <RefreshCw className={size === 'large' ? 'w-8 h-8' : 'w-6 h-6'} /> : icon}
      </div>
      <span className={cn(
        "font-medium",
        size === 'large' ? 'text-sm' : 'text-xs'
      )}>
        {label}
      </span>
    </button>
  );
};

// Pre-built action buttons for common use cases
interface QuickActionsProps {
  onRefresh?: () => void;
  onEmergencyStop?: () => void;
  onContactSupport?: () => void;
  isRefreshing?: boolean;
  className?: string;
}

export const MobileQuickActions = ({
  onRefresh,
  onEmergencyStop,
  onContactSupport,
  isRefreshing = false,
  className,
}: QuickActionsProps) => {
  return (
    <div className={cn("grid grid-cols-3 gap-3 p-4", className)}>
      {onRefresh && (
        <MobileActionButton
          icon={<RefreshCw className="w-6 h-6" />}
          label="Refresh Data"
          onClick={onRefresh}
          loading={isRefreshing}
        />
      )}
      
      {onEmergencyStop && (
        <MobileActionButton
          icon={<AlertOctagon className="w-6 h-6" />}
          label="Emergency Stop"
          onClick={onEmergencyStop}
          variant="destructive"
        />
      )}
      
      {onContactSupport && (
        <MobileActionButton
          icon={<Phone className="w-6 h-6" />}
          label="Get Support"
          onClick={onContactSupport}
          variant="default"
        />
      )}
    </div>
  );
};

// Floating Action Button component
interface FloatingActionButtonProps {
  icon: React.ReactNode;
  onClick: () => void;
  label?: string;
  variant?: 'default' | 'destructive';
  position?: 'bottom-right' | 'bottom-left' | 'bottom-center';
  className?: string;
}

export const FloatingActionButton = ({
  icon,
  onClick,
  label,
  variant = 'default',
  position = 'bottom-right',
  className,
}: FloatingActionButtonProps) => {
  const positionStyles = {
    'bottom-right': 'bottom-24 right-4',
    'bottom-left': 'bottom-24 left-4',
    'bottom-center': 'bottom-24 left-1/2 -translate-x-1/2',
  };

  const handleClick = () => {
    triggerHaptic();
    onClick();
  };

  return (
    <button
      onClick={handleClick}
      className={cn(
        "fixed z-40 flex items-center justify-center rounded-full shadow-lg transition-all touch-manipulation",
        "active:scale-95 hover:shadow-xl",
        "w-14 h-14",
        variant === 'destructive' 
          ? 'bg-destructive text-destructive-foreground' 
          : 'bg-primary text-primary-foreground',
        positionStyles[position],
        "md:hidden", // Only show on mobile
        className
      )}
      aria-label={label}
    >
      {icon}
    </button>
  );
};
