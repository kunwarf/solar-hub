import { forwardRef, ReactNode } from "react";
import { motion, HTMLMotionProps } from "framer-motion";
import { cn } from "@/lib/utils";

interface InteractiveCardProps extends Omit<HTMLMotionProps<"div">, "children"> {
  children: ReactNode;
  variant?: "default" | "glass" | "outline" | "elevated";
  hoverEffect?: "lift" | "glow" | "scale" | "border" | "none";
  pressEffect?: boolean;
  className?: string;
  disabled?: boolean;
}

const variantStyles = {
  default: "bg-card border border-border",
  glass: "glass-card",
  outline: "border border-border/50 bg-transparent",
  elevated: "bg-card shadow-lg border-0",
};

const hoverStyles = {
  lift: {
    rest: { y: 0, boxShadow: "0 1px 3px 0 rgb(0 0 0 / 0.1)" },
    hover: { y: -4, boxShadow: "0 10px 40px -10px rgb(0 0 0 / 0.2)" },
  },
  glow: {
    rest: { boxShadow: "0 0 0 0 hsl(var(--primary) / 0)" },
    hover: { boxShadow: "0 0 20px 0 hsl(var(--primary) / 0.2)" },
  },
  scale: {
    rest: { scale: 1 },
    hover: { scale: 1.02 },
  },
  border: {
    rest: { borderColor: "hsl(var(--border) / 0.5)" },
    hover: { borderColor: "hsl(var(--primary) / 0.5)" },
  },
  none: {
    rest: {},
    hover: {},
  },
};

export const InteractiveCard = forwardRef<HTMLDivElement, InteractiveCardProps>(
  (
    {
      children,
      variant = "default",
      hoverEffect = "lift",
      pressEffect = true,
      className,
      disabled = false,
      onClick,
      ...props
    },
    ref
  ) => {
    const isClickable = !!onClick && !disabled;
    const hover = hoverStyles[hoverEffect];

    return (
      <motion.div
        ref={ref}
        initial="rest"
        whileHover={!disabled ? "hover" : undefined}
        whileTap={pressEffect && isClickable ? { scale: 0.98 } : undefined}
        variants={{
          rest: hover.rest,
          hover: hover.hover,
        }}
        transition={{ type: "spring", stiffness: 400, damping: 25 }}
        onClick={onClick}
        className={cn(
          "rounded-lg transition-colors",
          variantStyles[variant],
          isClickable && "cursor-pointer",
          disabled && "opacity-50 cursor-not-allowed",
          className
        )}
        role={isClickable ? "button" : undefined}
        tabIndex={isClickable ? 0 : undefined}
        aria-disabled={disabled}
        {...props}
      >
        {children}
      </motion.div>
    );
  }
);

InteractiveCard.displayName = "InteractiveCard";

// Clickable card with focus ring for accessibility
export const ClickableCard = forwardRef<HTMLDivElement, InteractiveCardProps>(
  ({ className, ...props }, ref) => (
    <InteractiveCard
      ref={ref}
      className={cn(
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        className
      )}
      {...props}
    />
  )
);

ClickableCard.displayName = "ClickableCard";
