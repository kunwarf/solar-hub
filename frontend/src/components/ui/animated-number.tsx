import { useEffect, useRef, useState } from "react";
import { motion, useSpring, useTransform } from "framer-motion";
import { cn } from "@/lib/utils";

interface AnimatedNumberProps {
  value: number;
  duration?: number;
  formatOptions?: Intl.NumberFormatOptions;
  className?: string;
  prefix?: string;
  suffix?: string;
}

export function AnimatedNumber({
  value,
  duration = 1000,
  formatOptions,
  className,
  prefix = "",
  suffix = "",
}: AnimatedNumberProps) {
  const [displayValue, setDisplayValue] = useState(value);
  const prevValueRef = useRef(value);

  useEffect(() => {
    const startValue = prevValueRef.current;
    const endValue = value;
    const startTime = Date.now();

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Ease out cubic for smooth deceleration
      const easeOut = 1 - Math.pow(1 - progress, 3);
      const currentValue = startValue + (endValue - startValue) * easeOut;

      setDisplayValue(currentValue);

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        prevValueRef.current = endValue;
      }
    };

    requestAnimationFrame(animate);
  }, [value, duration]);

  const formattedValue = formatOptions
    ? new Intl.NumberFormat("en-US", formatOptions).format(Math.round(displayValue))
    : Math.round(displayValue).toLocaleString();

  return (
    <span className={cn("tabular-nums", className)}>
      {prefix}
      {formattedValue}
      {suffix}
    </span>
  );
}

// Compact version for currency with K/M suffix
export function AnimatedCurrency({
  value,
  currency = "USD",
  compact = false,
  className,
}: {
  value: number;
  currency?: string;
  compact?: boolean;
  className?: string;
}) {
  const formatOptions: Intl.NumberFormatOptions = {
    style: "currency",
    currency,
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 1 : 2,
  };

  return (
    <AnimatedNumber
      value={value}
      formatOptions={formatOptions}
      className={className}
    />
  );
}

// Percentage with animation
export function AnimatedPercentage({
  value,
  className,
}: {
  value: number;
  className?: string;
}) {
  return (
    <AnimatedNumber
      value={value}
      suffix="%"
      className={className}
    />
  );
}

// Success checkmark animation
export function SuccessCheckmark({ 
  show, 
  size = "md",
  className 
}: { 
  show: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const sizes = {
    sm: "w-5 h-5",
    md: "w-8 h-8",
    lg: "w-12 h-12",
  };

  if (!show) return null;

  return (
    <motion.div
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0, opacity: 0 }}
      className={cn(
        "rounded-full bg-success flex items-center justify-center",
        sizes[size],
        className
      )}
    >
      <motion.svg
        viewBox="0 0 24 24"
        className="w-3/5 h-3/5 text-success-foreground"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <motion.path
          d="M5 13l4 4L19 7"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        />
      </motion.svg>
    </motion.div>
  );
}

// Loading spinner with success transition
export function LoadingToSuccess({
  isLoading,
  isSuccess,
  size = "md",
  className,
}: {
  isLoading: boolean;
  isSuccess: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const sizes = {
    sm: "w-5 h-5",
    md: "w-8 h-8",
    lg: "w-12 h-12",
  };

  if (isSuccess) {
    return <SuccessCheckmark show={true} size={size} className={className} />;
  }

  if (isLoading) {
    return (
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
        className={cn(
          "rounded-full border-2 border-muted border-t-primary",
          sizes[size],
          className
        )}
      />
    );
  }

  return null;
}
