import { ReactNode, useState, useEffect } from "react";
import { AppSidebar } from "./AppSidebar";
import { MobileBottomNav } from "./MobileBottomNav";
import { OfflineBanner, SyncCompleteBanner } from "@/components/pwa/OfflineBanner";
import { InstallPromptBanner } from "@/components/pwa/InstallPrompt";
import { AskSolarHub } from "@/components/chat/AskSolarHub";
import { CommandPalette } from "@/components/navigation/CommandPalette";
import { Breadcrumbs } from "@/components/navigation/Breadcrumbs";
import { useOffline } from "@/hooks/use-offline";

interface AppLayoutProps {
  children: ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const { isSyncing, pendingActions } = useOffline();
  const [showSyncComplete, setShowSyncComplete] = useState(false);
  const [wasSyncing, setWasSyncing] = useState(false);

  // Track when sync completes
  useEffect(() => {
    if (isSyncing) {
      setWasSyncing(true);
    } else if (wasSyncing && pendingActions === 0) {
      setShowSyncComplete(true);
      setWasSyncing(false);
      // Auto-dismiss after 3 seconds
      const timer = setTimeout(() => setShowSyncComplete(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [isSyncing, wasSyncing, pendingActions]);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <CommandPalette />
      <OfflineBanner />
      <SyncCompleteBanner show={showSyncComplete} onDismiss={() => setShowSyncComplete(false)} />
      <div className="flex flex-1">
        <AppSidebar />
        <MobileBottomNav />
        <main className="flex-1 md:ml-[72px] lg:ml-64 transition-all duration-300 pb-20 md:pb-0">
          <div className="container mx-auto px-4 pt-4">
            <Breadcrumbs />
          </div>
          {children}
        </main>
      </div>
      <InstallPromptBanner />
      <AskSolarHub />
    </div>
  );
}
