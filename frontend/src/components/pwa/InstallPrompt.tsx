import { useState } from 'react';
import { Download, X, Smartphone, Share, PlusSquare, MoreVertical } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { usePWAInstall } from '@/hooks/use-offline';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

const DISMISSED_KEY = 'solar-hub-install-dismissed';

export const InstallPromptBanner = () => {
  const { canInstall, isInstalled, isIOS, promptInstall } = usePWAInstall();
  const [dismissed, setDismissed] = useState(() => {
    return localStorage.getItem(DISMISSED_KEY) === 'true';
  });
  const [showIOSDialog, setShowIOSDialog] = useState(false);

  const handleDismiss = () => {
    setDismissed(true);
    localStorage.setItem(DISMISSED_KEY, 'true');
  };

  const handleInstall = async () => {
    if (isIOS) {
      setShowIOSDialog(true);
    } else {
      await promptInstall();
    }
  };

  // Don't show if already installed or dismissed
  if (isInstalled || dismissed) return null;

  // Show for both installable and iOS devices
  if (!canInstall && !isIOS) return null;

  return (
    <>
      <AnimatePresence>
        <motion.div
          initial={{ y: 100, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 100, opacity: 0 }}
          className="fixed bottom-20 left-4 right-4 md:left-auto md:right-4 md:w-96 z-50"
        >
          <div className="bg-card border border-primary/30 rounded-xl p-4 shadow-lg shadow-primary/10">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-primary/10 rounded-lg">
                <Smartphone className="h-5 w-5 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-sm">Install Solar Hub</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Add to your home screen for quick access and offline support
                </p>
                <div className="flex items-center gap-2 mt-3">
                  <Button size="sm" onClick={handleInstall} className="gap-1.5">
                    <Download className="h-3.5 w-3.5" />
                    Install
                  </Button>
                  <Button size="sm" variant="ghost" onClick={handleDismiss}>
                    Not now
                  </Button>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 shrink-0"
                onClick={handleDismiss}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </motion.div>
      </AnimatePresence>

      <IOSInstallDialog open={showIOSDialog} onOpenChange={setShowIOSDialog} />
    </>
  );
};

const IOSInstallDialog = ({ 
  open, 
  onOpenChange 
}: { 
  open: boolean; 
  onOpenChange: (open: boolean) => void;
}) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Install Solar Hub</DialogTitle>
          <DialogDescription>
            Add Solar Hub to your home screen for the best experience
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4 py-4">
          <div className="flex items-start gap-4">
            <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary font-semibold text-sm shrink-0">
              1
            </div>
            <div className="flex-1">
              <p className="text-sm">
                Tap the <Share className="h-4 w-4 inline-block mx-1" /> Share button in Safari
              </p>
            </div>
          </div>
          
          <div className="flex items-start gap-4">
            <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary font-semibold text-sm shrink-0">
              2
            </div>
            <div className="flex-1">
              <p className="text-sm">
                Scroll down and tap <PlusSquare className="h-4 w-4 inline-block mx-1" /> <strong>Add to Home Screen</strong>
              </p>
            </div>
          </div>
          
          <div className="flex items-start gap-4">
            <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary font-semibold text-sm shrink-0">
              3
            </div>
            <div className="flex-1">
              <p className="text-sm">
                Tap <strong>Add</strong> in the top right corner
              </p>
            </div>
          </div>
        </div>

        <div className="bg-muted/50 rounded-lg p-3 text-xs text-muted-foreground">
          <p>
            Solar Hub will appear on your home screen and work offline just like a native app.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};

// Dedicated install page component
export const InstallPage = () => {
  const { canInstall, isInstalled, isIOS, promptInstall } = usePWAInstall();

  if (isInstalled) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center p-6">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto">
            <Smartphone className="h-8 w-8 text-success" />
          </div>
          <h1 className="text-2xl font-bold">Already Installed!</h1>
          <p className="text-muted-foreground max-w-sm">
            Solar Hub is already installed on your device. Look for it on your home screen.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="max-w-md w-full space-y-8 text-center">
        <div className="space-y-4">
          <div className="w-20 h-20 bg-primary/10 rounded-2xl flex items-center justify-center mx-auto">
            <Smartphone className="h-10 w-10 text-primary" />
          </div>
          <h1 className="text-3xl font-bold">Install Solar Hub</h1>
          <p className="text-muted-foreground">
            Get quick access to your solar monitoring dashboard right from your home screen
          </p>
        </div>

        <div className="space-y-3 text-left bg-card rounded-xl p-6 border">
          <h3 className="font-semibold">Benefits of installing:</h3>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-primary" />
              Launch instantly from your home screen
            </li>
            <li className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-primary" />
              Works offline with cached data
            </li>
            <li className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-primary" />
              Full-screen experience without browser UI
            </li>
            <li className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-primary" />
              Faster loading times
            </li>
          </ul>
        </div>

        {isIOS ? (
          <div className="space-y-4 text-left bg-card rounded-xl p-6 border">
            <h3 className="font-semibold">How to install on iOS:</h3>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="flex items-center justify-center w-7 h-7 rounded-full bg-primary text-primary-foreground font-semibold text-xs shrink-0">
                  1
                </div>
                <p className="text-sm text-muted-foreground">
                  Tap the <Share className="h-4 w-4 inline-block mx-1" /> Share button at the bottom of Safari
                </p>
              </div>
              <div className="flex items-start gap-3">
                <div className="flex items-center justify-center w-7 h-7 rounded-full bg-primary text-primary-foreground font-semibold text-xs shrink-0">
                  2
                </div>
                <p className="text-sm text-muted-foreground">
                  Scroll and tap <PlusSquare className="h-4 w-4 inline-block mx-1" /> <strong>Add to Home Screen</strong>
                </p>
              </div>
              <div className="flex items-start gap-3">
                <div className="flex items-center justify-center w-7 h-7 rounded-full bg-primary text-primary-foreground font-semibold text-xs shrink-0">
                  3
                </div>
                <p className="text-sm text-muted-foreground">
                  Tap <strong>Add</strong> to confirm
                </p>
              </div>
            </div>
          </div>
        ) : canInstall ? (
          <Button size="lg" onClick={promptInstall} className="w-full gap-2">
            <Download className="h-5 w-5" />
            Install Solar Hub
          </Button>
        ) : (
          <div className="space-y-4 text-left bg-card rounded-xl p-6 border">
            <h3 className="font-semibold">How to install:</h3>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="flex items-center justify-center w-7 h-7 rounded-full bg-primary text-primary-foreground font-semibold text-xs shrink-0">
                  1
                </div>
                <p className="text-sm text-muted-foreground">
                  Tap the <MoreVertical className="h-4 w-4 inline-block mx-1" /> menu in your browser
                </p>
              </div>
              <div className="flex items-start gap-3">
                <div className="flex items-center justify-center w-7 h-7 rounded-full bg-primary text-primary-foreground font-semibold text-xs shrink-0">
                  2
                </div>
                <p className="text-sm text-muted-foreground">
                  Select <strong>Install app</strong> or <strong>Add to Home Screen</strong>
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
