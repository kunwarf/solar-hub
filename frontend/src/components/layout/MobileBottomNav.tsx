import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  Cpu,
  Settings,
  ChevronUp,
  X,
  Sun,
  Moon,
  Brain,
  Bell,
  HelpCircle,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/hooks/use-theme";
import { Badge } from "@/components/ui/badge";

// Mock alert count - in real app this would come from context/state
const useAlertCount = () => {
  // This would normally come from a context or API
  return 3;
};

const primaryNavItems = [
  { title: "Home", url: "/", icon: LayoutDashboard },
  { title: "Devices", url: "/devices", icon: Cpu },
  { title: "Alerts", url: "/alerts", icon: Bell, showBadge: true },
  { title: "Scheduler", url: "/scheduler", icon: Brain },
];

const secondaryNavItems = [
  { title: "Settings", url: "/settings", icon: Settings },
  { title: "Profile", url: "/profile", icon: User },
  { title: "Help", url: "/help", icon: HelpCircle },
];

// Haptic feedback helper
const triggerHaptic = (pattern: number | number[] = 10) => {
  if ('vibrate' in navigator) {
    navigator.vibrate(pattern);
  }
};

export function MobileBottomNav() {
  const [expanded, setExpanded] = useState(false);
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const alertCount = useAlertCount();

  const handleNavClick = () => {
    triggerHaptic();
    setExpanded(false);
  };

  const handleExpandToggle = () => {
    triggerHaptic();
    setExpanded(!expanded);
  };

  return (
    <>
      {/* Overlay */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40 md:hidden"
            onClick={() => setExpanded(false)}
          />
        )}
      </AnimatePresence>

      {/* Bottom Navigation */}
      <motion.nav
        initial={false}
        animate={{ height: expanded ? "auto" : 72 }}
        className="fixed bottom-0 left-0 right-0 bg-sidebar border-t border-sidebar-border z-50 md:hidden safe-area-bottom"
      >
        {/* Expanded Menu */}
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              className="p-4 space-y-2 border-b border-sidebar-border"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-muted-foreground">More Options</span>
                <button
                  onClick={() => {
                    triggerHaptic();
                    setExpanded(false);
                  }}
                  className="p-2 rounded-lg hover:bg-sidebar-accent text-muted-foreground active:scale-95 transition-transform touch-manipulation"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Secondary Nav Items */}
              {secondaryNavItems.map((item) => {
                const isActive = location.pathname === item.url;
                return (
                  <NavLink
                    key={item.title}
                    to={item.url}
                    onClick={handleNavClick}
                    className={cn(
                      "flex items-center gap-3 px-4 py-3.5 rounded-lg transition-all touch-manipulation active:scale-[0.98]",
                      isActive
                        ? "bg-primary/10 text-primary border border-primary/20"
                        : "text-sidebar-foreground hover:bg-sidebar-accent border border-transparent"
                    )}
                  >
                    <item.icon className="w-5 h-5" />
                    <span className="font-medium">{item.title}</span>
                  </NavLink>
                );
              })}

              {/* Theme Toggle */}
              <button
                onClick={() => {
                  triggerHaptic();
                  toggleTheme();
                }}
                className="w-full flex items-center gap-3 px-4 py-3.5 rounded-lg transition-all text-sidebar-foreground hover:bg-sidebar-accent border border-transparent touch-manipulation active:scale-[0.98]"
              >
                {theme === "dark" ? (
                  <>
                    <Sun className="w-5 h-5" />
                    <span className="font-medium">Light Mode</span>
                  </>
                ) : (
                  <>
                    <Moon className="w-5 h-5" />
                    <span className="font-medium">Dark Mode</span>
                  </>
                )}
              </button>

              {/* System Status */}
              <div className="mt-4 p-3 glass-card">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full status-online" />
                  <span className="text-xs text-muted-foreground">System Online</span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Primary Nav Bar */}
        <div className="flex items-center justify-around h-[72px] px-2">
          {primaryNavItems.map((item) => {
            const isActive = location.pathname === item.url;
            return (
              <NavLink
                key={item.title}
                to={item.url}
                onClick={handleNavClick}
                className={cn(
                  "flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-all min-w-[56px] touch-manipulation active:scale-95",
                  isActive
                    ? "text-primary"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <div className={cn(
                  "relative p-2 rounded-xl transition-all",
                  isActive && "bg-primary/10"
                )}>
                  <item.icon className="w-5 h-5" />
                  {/* Alert Badge */}
                  {item.showBadge && alertCount > 0 && (
                    <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] flex items-center justify-center bg-destructive text-destructive-foreground text-[10px] font-bold rounded-full px-1">
                      {alertCount > 9 ? '9+' : alertCount}
                    </span>
                  )}
                </div>
                <span className="text-[10px] font-medium">{item.title}</span>
              </NavLink>
            );
          })}

          {/* Expand Button */}
          <button
            onClick={handleExpandToggle}
            className={cn(
              "flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-all min-w-[56px] touch-manipulation active:scale-95",
              expanded
                ? "text-primary"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <div className={cn(
              "p-2 rounded-xl transition-all",
              expanded && "bg-primary/10"
            )}>
              <ChevronUp className={cn(
                "w-5 h-5 transition-transform duration-300",
                expanded && "rotate-180"
              )} />
            </div>
            <span className="text-[10px] font-medium">More</span>
          </button>
        </div>
      </motion.nav>
    </>
  );
}
