import { WifiOff, RefreshCw, Clock, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useOffline } from '@/hooks/use-offline';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { motion, AnimatePresence } from 'framer-motion';

export const OfflineBanner = () => {
  const { isOffline, lastOnlineAt, isSyncing, pendingActions, syncActions } = useOffline();

  return (
    <AnimatePresence>
      {isOffline && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="bg-warning/10 border-b border-warning/30 overflow-hidden"
        >
          <div className="container mx-auto px-4 py-2">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div className="flex items-center gap-3">
                <div className="p-1.5 bg-warning/20 rounded-full">
                  <WifiOff className="h-4 w-4 text-warning" />
                </div>
                <div className="text-sm">
                  <span className="font-medium text-warning">You're offline</span>
                  <span className="text-muted-foreground ml-2">
                    Showing cached data
                  </span>
                </div>
              </div>
              
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                {lastOnlineAt && (
                  <div className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5" />
                    <span>Last online {formatDistanceToNow(lastOnlineAt)} ago</span>
                  </div>
                )}
                
                {pendingActions > 0 && (
                  <div className="flex items-center gap-1.5 text-warning">
                    <span>{pendingActions} action{pendingActions !== 1 ? 's' : ''} queued</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {isSyncing && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="bg-info/10 border-b border-info/30 overflow-hidden"
        >
          <div className="container mx-auto px-4 py-2">
            <div className="flex items-center gap-3">
              <RefreshCw className="h-4 w-4 text-info animate-spin" />
              <span className="text-sm font-medium text-info">Syncing...</span>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export const SyncCompleteBanner = ({ show, onDismiss }: { show: boolean; onDismiss: () => void }) => {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="bg-success/10 border-b border-success/30 overflow-hidden"
        >
          <div className="container mx-auto px-4 py-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="h-4 w-4 text-success" />
                <span className="text-sm font-medium text-success">Sync complete</span>
              </div>
              <Button variant="ghost" size="sm" onClick={onDismiss}>
                Dismiss
              </Button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
