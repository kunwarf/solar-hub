import { useState, ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { HelpCircle, X, ExternalLink, Lightbulb, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";

interface InfoTooltipProps {
  content: string;
  learnMoreUrl?: string;
  className?: string;
  side?: "top" | "right" | "bottom" | "left";
  size?: "sm" | "md";
}

// Info icon with tooltip for technical terms
export function InfoTooltip({
  content,
  learnMoreUrl,
  className,
  side = "top",
  size = "sm",
}: InfoTooltipProps) {
  const sizes = {
    sm: "w-3.5 h-3.5",
    md: "w-4 h-4",
  };

  return (
    <TooltipProvider>
      <Tooltip delayDuration={300}>
        <TooltipTrigger asChild>
          <button
            className={cn(
              "inline-flex items-center justify-center text-muted-foreground/50 hover:text-muted-foreground transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-full",
              className
            )}
            aria-label="More information"
          >
            <HelpCircle className={sizes[size]} />
          </button>
        </TooltipTrigger>
        <TooltipContent side={side} className="max-w-[250px] p-3">
          <p className="text-xs leading-relaxed">{content}</p>
          {learnMoreUrl && (
            <a
              href={learnMoreUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline mt-2"
            >
              Learn more
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// First-time user hint (dismissible)
interface FirstTimeHintProps {
  id: string; // Unique ID for localStorage
  children: ReactNode;
  hint: string;
  position?: "top" | "bottom" | "left" | "right";
  className?: string;
}

export function FirstTimeHint({
  id,
  children,
  hint,
  position = "bottom",
  className,
}: FirstTimeHintProps) {
  const storageKey = `hint_dismissed_${id}`;
  const [isDismissed, setIsDismissed] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem(storageKey) === "true";
    }
    return false;
  });

  const dismiss = () => {
    setIsDismissed(true);
    localStorage.setItem(storageKey, "true");
  };

  const positionStyles = {
    top: "bottom-full mb-2 left-1/2 -translate-x-1/2",
    bottom: "top-full mt-2 left-1/2 -translate-x-1/2",
    left: "right-full mr-2 top-1/2 -translate-y-1/2",
    right: "left-full ml-2 top-1/2 -translate-y-1/2",
  };

  const arrowStyles = {
    top: "bottom-[-6px] left-1/2 -translate-x-1/2 rotate-180",
    bottom: "top-[-6px] left-1/2 -translate-x-1/2",
    left: "right-[-6px] top-1/2 -translate-y-1/2 rotate-90",
    right: "left-[-6px] top-1/2 -translate-y-1/2 -rotate-90",
  };

  return (
    <div className={cn("relative inline-block", className)}>
      {children}
      <AnimatePresence>
        {!isDismissed && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className={cn(
              "absolute z-50 w-64 p-3 rounded-lg bg-primary text-primary-foreground shadow-lg",
              positionStyles[position]
            )}
          >
            {/* Arrow */}
            <div
              className={cn(
                "absolute w-3 h-3 bg-primary rotate-45",
                arrowStyles[position]
              )}
            />

            <div className="relative flex items-start gap-2">
              <Lightbulb className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <p className="text-xs leading-relaxed flex-1">{hint}</p>
              <button
                onClick={dismiss}
                className="flex-shrink-0 hover:bg-primary-foreground/10 rounded p-0.5 transition-colors"
                aria-label="Dismiss hint"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Contextual tip that appears based on user actions
interface ContextualTipProps {
  show: boolean;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  onDismiss: () => void;
  className?: string;
}

export function ContextualTip({
  show,
  title,
  description,
  action,
  onDismiss,
  className,
}: ContextualTipProps) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, y: 10, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 10, scale: 0.95 }}
          className={cn(
            "fixed bottom-4 right-4 z-50 w-80 p-4 rounded-xl bg-card border border-border shadow-xl",
            className
          )}
        >
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
              <Lightbulb className="w-4 h-4 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <h4 className="text-sm font-medium text-foreground">{title}</h4>
                <button
                  onClick={onDismiss}
                  className="text-muted-foreground hover:text-foreground transition-colors"
                  aria-label="Dismiss tip"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                {description}
              </p>
              {action && (
                <Button
                  variant="link"
                  size="sm"
                  onClick={action.onClick}
                  className="h-auto p-0 mt-2 text-xs"
                >
                  {action.label}
                  <ChevronRight className="w-3 h-3 ml-1" />
                </Button>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// Label with info icon
interface LabelWithInfoProps {
  label: string;
  info: string;
  learnMoreUrl?: string;
  className?: string;
  required?: boolean;
}

export function LabelWithInfo({
  label,
  info,
  learnMoreUrl,
  className,
  required = false,
}: LabelWithInfoProps) {
  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      <span className="text-sm font-medium text-foreground">
        {label}
        {required && <span className="text-destructive ml-0.5">*</span>}
      </span>
      <InfoTooltip content={info} learnMoreUrl={learnMoreUrl} />
    </div>
  );
}
