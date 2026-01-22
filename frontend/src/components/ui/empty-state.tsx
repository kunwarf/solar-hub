import { ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { 
  Sun, 
  Bell, 
  Calendar, 
  Search, 
  Cpu, 
  AlertCircle, 
  CheckCircle2,
  Sparkles,
  PartyPopper,
  Zap
} from "lucide-react";

interface EmptyStateProps {
  type: "no-devices" | "no-alerts" | "no-outages" | "no-results" | "all-good" | "error";
  title?: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
  children?: ReactNode;
}

const emptyStateConfig = {
  "no-devices": {
    icon: Cpu,
    defaultTitle: "No Devices Yet",
    defaultDescription: "Add your first solar device to start monitoring your energy production.",
    illustration: "device",
    color: "text-primary",
    bgColor: "bg-primary/10",
  },
  "no-alerts": {
    icon: CheckCircle2,
    defaultTitle: "All Systems Normal",
    defaultDescription: "No alerts to show. Your solar system is running smoothly!",
    illustration: "happy",
    color: "text-success",
    bgColor: "bg-success/10",
  },
  "no-outages": {
    icon: PartyPopper,
    defaultTitle: "No Outages This Month",
    defaultDescription: "Great news! You haven't experienced any power outages this month.",
    illustration: "celebration",
    color: "text-solar",
    bgColor: "bg-solar/10",
  },
  "no-results": {
    icon: Search,
    defaultTitle: "No Results Found",
    defaultDescription: "Try adjusting your search or filter criteria.",
    illustration: "search",
    color: "text-muted-foreground",
    bgColor: "bg-muted",
  },
  "all-good": {
    icon: Sparkles,
    defaultTitle: "Everything's Working",
    defaultDescription: "Your solar system is performing optimally.",
    illustration: "sparkle",
    color: "text-solar",
    bgColor: "bg-solar/10",
  },
  "error": {
    icon: AlertCircle,
    defaultTitle: "Something Went Wrong",
    defaultDescription: "We couldn't load this content. Please try again.",
    illustration: "error",
    color: "text-destructive",
    bgColor: "bg-destructive/10",
  },
};

// Simple SVG illustrations
const Illustrations = {
  device: () => (
    <svg viewBox="0 0 120 120" className="w-24 h-24">
      <rect x="20" y="30" width="80" height="50" rx="4" className="fill-muted stroke-muted-foreground/30" strokeWidth="2" />
      <rect x="30" y="40" width="60" height="30" rx="2" className="fill-background" />
      <line x1="50" y1="85" x2="50" y2="95" className="stroke-muted-foreground/50" strokeWidth="3" />
      <line x1="70" y1="85" x2="70" y2="95" className="stroke-muted-foreground/50" strokeWidth="3" />
      <circle cx="60" cy="55" r="8" className="fill-primary/20 stroke-primary" strokeWidth="2" />
      <path d="M60 50 L60 60 M55 55 L65 55" className="stroke-primary" strokeWidth="2" strokeLinecap="round" />
    </svg>
  ),
  happy: () => (
    <svg viewBox="0 0 120 120" className="w-24 h-24">
      <circle cx="60" cy="60" r="40" className="fill-success/10 stroke-success/30" strokeWidth="2" />
      <circle cx="45" cy="50" r="5" className="fill-success" />
      <circle cx="75" cy="50" r="5" className="fill-success" />
      <path d="M40 70 Q60 85 80 70" fill="none" className="stroke-success" strokeWidth="3" strokeLinecap="round" />
      {/* Sun rays */}
      <g className="animate-pulse">
        <line x1="60" y1="10" x2="60" y2="18" className="stroke-solar" strokeWidth="2" strokeLinecap="round" />
        <line x1="95" y1="25" x2="89" y2="31" className="stroke-solar" strokeWidth="2" strokeLinecap="round" />
        <line x1="25" y1="25" x2="31" y2="31" className="stroke-solar" strokeWidth="2" strokeLinecap="round" />
      </g>
    </svg>
  ),
  celebration: () => (
    <svg viewBox="0 0 120 120" className="w-24 h-24">
      <rect x="45" y="50" width="30" height="35" rx="2" className="fill-solar/20 stroke-solar" strokeWidth="2" />
      <polygon points="60,20 75,50 45,50" className="fill-solar/30 stroke-solar" strokeWidth="2" />
      {/* Confetti */}
      <g className="animate-bounce">
        <circle cx="30" cy="40" r="3" className="fill-primary" />
        <circle cx="90" cy="35" r="3" className="fill-success" />
        <circle cx="25" cy="70" r="2" className="fill-solar" />
        <circle cx="95" cy="65" r="2" className="fill-battery" />
        <rect x="35" y="25" width="4" height="4" className="fill-grid rotate-45" />
        <rect x="80" y="55" width="4" height="4" className="fill-primary rotate-45" />
      </g>
    </svg>
  ),
  search: () => (
    <svg viewBox="0 0 120 120" className="w-24 h-24">
      <circle cx="50" cy="50" r="25" fill="none" className="stroke-muted-foreground/30" strokeWidth="4" />
      <line x1="68" y1="68" x2="90" y2="90" className="stroke-muted-foreground/30" strokeWidth="4" strokeLinecap="round" />
      <path d="M40 50 Q50 40 60 50" fill="none" className="stroke-muted-foreground/50" strokeWidth="2" strokeLinecap="round" />
    </svg>
  ),
  sparkle: () => (
    <svg viewBox="0 0 120 120" className="w-24 h-24">
      <circle cx="60" cy="60" r="30" className="fill-solar/10" />
      <g className="animate-pulse">
        <path d="M60 35 L63 55 L75 50 L65 60 L75 70 L63 65 L60 85 L57 65 L45 70 L55 60 L45 50 L57 55 Z" className="fill-solar" />
      </g>
      <circle cx="85" cy="35" r="4" className="fill-solar/50" />
      <circle cx="35" cy="80" r="3" className="fill-solar/30" />
    </svg>
  ),
  error: () => (
    <svg viewBox="0 0 120 120" className="w-24 h-24">
      <circle cx="60" cy="60" r="35" className="fill-destructive/10 stroke-destructive/30" strokeWidth="2" />
      <line x1="45" y1="45" x2="75" y2="75" className="stroke-destructive" strokeWidth="4" strokeLinecap="round" />
      <line x1="75" y1="45" x2="45" y2="75" className="stroke-destructive" strokeWidth="4" strokeLinecap="round" />
    </svg>
  ),
};

export function EmptyState({
  type,
  title,
  description,
  action,
  className,
  children,
}: EmptyStateProps) {
  const config = emptyStateConfig[type];
  const Icon = config.icon;
  const IllustrationComponent = Illustrations[config.illustration as keyof typeof Illustrations];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "flex flex-col items-center justify-center py-12 px-6 text-center",
        className
      )}
    >
      {/* Illustration */}
      <motion.div
        initial={{ scale: 0.8 }}
        animate={{ scale: 1 }}
        transition={{ delay: 0.1, type: "spring", stiffness: 200 }}
        className="mb-6"
      >
        <IllustrationComponent />
      </motion.div>

      {/* Icon Badge */}
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: 0.2, type: "spring", stiffness: 300 }}
        className={cn(
          "w-12 h-12 rounded-full flex items-center justify-center mb-4",
          config.bgColor
        )}
      >
        <Icon className={cn("w-6 h-6", config.color)} />
      </motion.div>

      {/* Title */}
      <motion.h3
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="text-lg font-semibold text-foreground mb-2"
      >
        {title || config.defaultTitle}
      </motion.h3>

      {/* Description */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
        className="text-sm text-muted-foreground max-w-sm mb-6"
      >
        {description || config.defaultDescription}
      </motion.p>

      {/* Action Button */}
      {action && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <Button onClick={action.onClick} className="gap-2">
            {type === "no-devices" && <Cpu className="w-4 h-4" />}
            {type === "error" && <Zap className="w-4 h-4" />}
            {action.label}
          </Button>
        </motion.div>
      )}

      {/* Custom children */}
      {children}
    </motion.div>
  );
}

// Search suggestions component for no-results empty state
export function SearchSuggestions({ 
  suggestions, 
  onSuggestionClick 
}: { 
  suggestions: string[];
  onSuggestionClick: (suggestion: string) => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.6 }}
      className="mt-4"
    >
      <p className="text-xs text-muted-foreground mb-2">Try searching for:</p>
      <div className="flex flex-wrap gap-2 justify-center">
        {suggestions.map((suggestion, index) => (
          <motion.button
            key={suggestion}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.7 + index * 0.05 }}
            onClick={() => onSuggestionClick(suggestion)}
            className="px-3 py-1 text-xs rounded-full bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-colors"
          >
            {suggestion}
          </motion.button>
        ))}
      </div>
    </motion.div>
  );
}
