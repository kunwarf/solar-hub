import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  LayoutDashboard,
  Cpu,
  Settings,
  Bell,
  Zap,
  Brain,
  AlertTriangle,
  ZapOff,
  Receipt,
  User,
  Clock,
  Search,
  Plus,
  History,
  Home,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface RecentSearch {
  id: string;
  query: string;
  timestamp: number;
}

interface NavItem {
  title: string;
  url: string;
  icon: any;
  shortcut?: string;
  description?: string;
}

const navigationItems: NavItem[] = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard, shortcut: "G D" },
  { title: "Devices", url: "/devices", icon: Cpu, shortcut: "G V" },
  { title: "Device Management", url: "/devices/manage", icon: Settings, shortcut: "G M" },
  { title: "Telemetry", url: "/telemetry", icon: Zap, shortcut: "G T" },
  { title: "Settings", url: "/settings", icon: Settings, shortcut: "G S" },
  { title: "Alert Center", url: "/alerts", icon: AlertTriangle, shortcut: "G A" },
  { title: "Smart Scheduler", url: "/scheduler", icon: Brain, shortcut: "G H" },
  { title: "Outages", url: "/outages", icon: ZapOff },
  { title: "Billing", url: "/billing", icon: Receipt, shortcut: "G B" },
  { title: "Profile", url: "/profile", icon: User, shortcut: "G P" },
  { title: "Notifications", url: "/notifications", icon: Bell },
];

const quickActions: NavItem[] = [
  { title: "Claim Device", url: "/claim-device", icon: Plus, description: "Add a new device to your system" },
  { title: "View Notifications", url: "/notifications", icon: Bell, description: "Check your notifications" },
  { title: "Installation Wizard", url: "/install", icon: Clock, description: "Set up a new installation" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [recentSearches, setRecentSearches] = useState<RecentSearch[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const navigate = useNavigate();

  // Load recent searches from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("commandPaletteRecent");
    if (saved) {
      try {
        setRecentSearches(JSON.parse(saved));
      } catch {
        setRecentSearches([]);
      }
    }
  }, []);

  // Save recent search
  const saveRecentSearch = useCallback((query: string) => {
    if (!query.trim()) return;

    const newRecent: RecentSearch = {
      id: Date.now().toString(),
      query: query.trim(),
      timestamp: Date.now(),
    };

    setRecentSearches((prev) => {
      const filtered = prev.filter((s) => s.query.toLowerCase() !== query.toLowerCase());
      const updated = [newRecent, ...filtered].slice(0, 5);
      localStorage.setItem("commandPaletteRecent", JSON.stringify(updated));
      return updated;
    });
  }, []);

  // Handle Cmd/Ctrl + K to open
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
        setSearchQuery("");
        setSelectedIndex(0);
        return;
      }
    };

    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  // Handle "G then X" keyboard shortcuts
  useEffect(() => {
    let gPressed = false;
    let timeout: NodeJS.Timeout;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if command palette is open or if we're in an input
      if (open) return;
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
        return;
      }

      if (e.key.toLowerCase() === "g" && !e.metaKey && !e.ctrlKey) {
        gPressed = true;
        timeout = setTimeout(() => {
          gPressed = false;
        }, 1000);
        return;
      }

      if (gPressed) {
        gPressed = false;
        clearTimeout(timeout);

        const shortcuts: Record<string, string> = {
          d: "/",
          v: "/devices",
          m: "/devices/manage",
          t: "/telemetry",
          s: "/settings",
          a: "/alerts",
          h: "/scheduler",
          b: "/billing",
          p: "/profile",
        };

        const path = shortcuts[e.key.toLowerCase()];
        if (path) {
          e.preventDefault();
          navigate(path);
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (timeout) clearTimeout(timeout);
    };
  }, [open, navigate]);

  // Filter items based on search
  const filteredNavItems = navigationItems.filter((item) =>
    item.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredActions = quickActions.filter((item) =>
    item.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const allFilteredItems = [...filteredNavItems, ...filteredActions];

  // Handle keyboard navigation
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, allFilteredItems.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (allFilteredItems[selectedIndex]) {
          handleSelect(allFilteredItems[selectedIndex]);
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, selectedIndex, allFilteredItems]);

  const handleSelect = (item: NavItem) => {
    saveRecentSearch(item.title);
    setOpen(false);
    navigate(item.url);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-2xl p-0 gap-0">
        <div className="flex items-center border-b px-3">
          <Search className="h-4 w-4 text-muted-foreground mr-2" />
          <Input
            placeholder="Search or type a command... (Cmd/Ctrl + K)"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setSelectedIndex(0);
            }}
            className="border-0 focus-visible:ring-0 focus-visible:ring-offset-0"
            autoFocus
          />
        </div>

        <div className="max-h-[400px] overflow-y-auto p-2">
          {searchQuery === "" && recentSearches.length > 0 && (
            <div className="mb-2">
              <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                Recent Searches
              </div>
              {recentSearches.map((search) => (
                <div
                  key={search.id}
                  className="flex items-center gap-2 px-2 py-1.5 text-sm text-muted-foreground rounded hover:bg-accent cursor-pointer"
                  onClick={() => setSearchQuery(search.query)}
                >
                  <History className="h-4 w-4" />
                  {search.query}
                </div>
              ))}
            </div>
          )}

          {filteredNavItems.length > 0 && (
            <div className="mb-2">
              <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                Navigation
              </div>
              {filteredNavItems.map((item, index) => {
                const Icon = item.icon;
                const globalIndex = index;
                return (
                  <button
                    key={item.url}
                    onClick={() => handleSelect(item)}
                    className={cn(
                      "w-full flex items-center justify-between gap-2 px-2 py-2 text-sm rounded hover:bg-accent cursor-pointer",
                      selectedIndex === globalIndex && "bg-accent"
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </div>
                    {item.shortcut && (
                      <kbd className="px-2 py-0.5 text-xs bg-muted rounded">
                        {item.shortcut}
                      </kbd>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          {filteredActions.length > 0 && (
            <div>
              <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                Quick Actions
              </div>
              {filteredActions.map((item, index) => {
                const Icon = item.icon;
                const globalIndex = filteredNavItems.length + index;
                return (
                  <button
                    key={item.url}
                    onClick={() => handleSelect(item)}
                    className={cn(
                      "w-full flex items-start gap-2 px-2 py-2 text-sm rounded hover:bg-accent cursor-pointer text-left",
                      selectedIndex === globalIndex && "bg-accent"
                    )}
                  >
                    <Icon className="h-4 w-4 mt-0.5" />
                    <div>
                      <div>{item.title}</div>
                      {item.description && (
                        <div className="text-xs text-muted-foreground">
                          {item.description}
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {searchQuery && allFilteredItems.length === 0 && (
            <div className="py-6 text-center text-sm text-muted-foreground">
              No results found for "{searchQuery}"
            </div>
          )}
        </div>

        <div className="border-t px-3 py-2 text-xs text-muted-foreground">
          <div className="flex items-center justify-between">
            <span>Press <kbd className="px-1.5 py-0.5 bg-muted rounded">↑↓</kbd> to navigate</span>
            <span>Press <kbd className="px-1.5 py-0.5 bg-muted rounded">Enter</kbd> to select</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
