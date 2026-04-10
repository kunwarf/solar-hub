import { useState, useEffect, useCallback } from 'react';

interface OfflineState {
  isOnline: boolean;
  isOffline: boolean;
  lastOnlineAt: Date | null;
  isSyncing: boolean;
  pendingActions: number;
}

interface QueuedAction {
  id: string;
  type: string;
  payload: unknown;
  timestamp: number;
}

const STORAGE_KEY = 'solar-hub-offline-queue';
const LAST_ONLINE_KEY = 'solar-hub-last-online';
const CACHED_DATA_KEY = 'solar-hub-cached-data';

export const useOffline = () => {
  const [state, setState] = useState<OfflineState>({
    isOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
    isOffline: typeof navigator !== 'undefined' ? !navigator.onLine : false,
    lastOnlineAt: null,
    isSyncing: false,
    pendingActions: 0,
  });

  // Load initial state from localStorage
  useEffect(() => {
    const lastOnline = localStorage.getItem(LAST_ONLINE_KEY);
    const queue = localStorage.getItem(STORAGE_KEY);
    
    setState(prev => ({
      ...prev,
      lastOnlineAt: lastOnline ? new Date(lastOnline) : null,
      pendingActions: queue ? JSON.parse(queue).length : 0,
    }));
  }, []);

  // Handle online/offline events
  useEffect(() => {
    const handleOnline = () => {
      setState(prev => ({
        ...prev,
        isOnline: true,
        isOffline: false,
        lastOnlineAt: new Date(),
      }));
      localStorage.setItem(LAST_ONLINE_KEY, new Date().toISOString());
    };

    const handleOffline = () => {
      setState(prev => ({
        ...prev,
        isOnline: false,
        isOffline: true,
      }));
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Queue an action for later sync
  const queueAction = useCallback((type: string, payload: unknown) => {
    const action: QueuedAction = {
      id: crypto.randomUUID(),
      type,
      payload,
      timestamp: Date.now(),
    };

    const existingQueue = localStorage.getItem(STORAGE_KEY);
    const queue: QueuedAction[] = existingQueue ? JSON.parse(existingQueue) : [];
    queue.push(action);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));

    setState(prev => ({
      ...prev,
      pendingActions: queue.length,
    }));

    return action.id;
  }, []);

  // Get queued actions
  const getQueuedActions = useCallback((): QueuedAction[] => {
    const queue = localStorage.getItem(STORAGE_KEY);
    return queue ? JSON.parse(queue) : [];
  }, []);

  // Clear a specific action from queue
  const clearAction = useCallback((actionId: string) => {
    const queue = getQueuedActions().filter(a => a.id !== actionId);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
    setState(prev => ({
      ...prev,
      pendingActions: queue.length,
    }));
  }, [getQueuedActions]);

  // Clear all queued actions
  const clearAllActions = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([]));
    setState(prev => ({
      ...prev,
      pendingActions: 0,
    }));
  }, []);

  // Sync queued actions (mock implementation)
  const syncActions = useCallback(async () => {
    const queue = getQueuedActions();
    if (queue.length === 0) return;

    setState(prev => ({ ...prev, isSyncing: true }));

    // Simulate sync delay
    await new Promise(resolve => setTimeout(resolve, 1500));

    // In a real app, you would send each action to your backend here
    // For now, we just clear the queue
    clearAllActions();

    setState(prev => ({ ...prev, isSyncing: false }));
  }, [getQueuedActions, clearAllActions]);

  // Cache data for offline access
  const cacheData = useCallback((key: string, data: unknown) => {
    const cache = localStorage.getItem(CACHED_DATA_KEY);
    const cacheObj = cache ? JSON.parse(cache) : {};
    cacheObj[key] = {
      data,
      timestamp: Date.now(),
    };
    localStorage.setItem(CACHED_DATA_KEY, JSON.stringify(cacheObj));
  }, []);

  // Get cached data — returns null if older than maxAgeMs (default 5 minutes)
  const getCachedData = useCallback(<T,>(key: string, maxAgeMs: number = 5 * 60 * 1000): { data: T; timestamp: number } | null => {
    const cache = localStorage.getItem(CACHED_DATA_KEY);
    if (!cache) return null;
    const cacheObj = JSON.parse(cache);
    const entry = cacheObj[key];
    if (!entry) return null;
    if (Date.now() - entry.timestamp > maxAgeMs) return null;
    return entry;
  }, []);

  // Auto-sync when coming back online
  useEffect(() => {
    if (state.isOnline && state.pendingActions > 0) {
      syncActions();
    }
  }, [state.isOnline, state.pendingActions, syncActions]);

  return {
    ...state,
    queueAction,
    getQueuedActions,
    clearAction,
    clearAllActions,
    syncActions,
    cacheData,
    getCachedData,
  };
};

// Hook for PWA install prompt
export const usePWAInstall = () => {
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isInstalled, setIsInstalled] = useState(false);
  const [isIOS, setIsIOS] = useState(false);

  useEffect(() => {
    // Check if already installed
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsInstalled(true);
    }

    // Check if iOS
    const isIOSDevice = /iPad|iPhone|iPod/.test(navigator.userAgent) && !(window as unknown as { MSStream?: unknown }).MSStream;
    setIsIOS(isIOSDevice);

    // Listen for install prompt
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setInstallPrompt(e as BeforeInstallPromptEvent);
    };

    const handleAppInstalled = () => {
      setIsInstalled(true);
      setInstallPrompt(null);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);

  const promptInstall = useCallback(async () => {
    if (!installPrompt) return false;

    installPrompt.prompt();
    const { outcome } = await installPrompt.userChoice;
    
    if (outcome === 'accepted') {
      setIsInstalled(true);
    }
    
    setInstallPrompt(null);
    return outcome === 'accepted';
  }, [installPrompt]);

  return {
    canInstall: !!installPrompt,
    isInstalled,
    isIOS,
    promptInstall,
  };
};

// Type for BeforeInstallPromptEvent
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}
