import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useSetupWizard } from '@/hooks/use-setup-wizard';
import { motion } from 'framer-motion';
import { ArrowLeft, ArrowRight, Camera, Keyboard, QrCode, Info } from 'lucide-react';

const DeviceStep = () => {
  const { nextStep, prevStep, data, updateData } = useSetupWizard();
  const [activeTab, setActiveTab] = useState<string>('qr');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState(false);

  const handleQRScan = async () => {
    setIsScanning(true);
    setCameraError(null);
    
    try {
      // Request camera permission
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      // In a real implementation, we'd use a QR scanner library here
      // For demo, simulate a successful scan after 2 seconds
      setTimeout(() => {
        stream.getTracks().forEach(track => track.stop());
        updateData({ deviceCode: 'SM-2024-' + Math.random().toString(36).substr(2, 8).toUpperCase() });
        setIsScanning(false);
      }, 2000);
    } catch (err) {
      setCameraError('Camera access denied. Please use manual entry instead.');
      setIsScanning(false);
    }
  };

  const isValid = data.deviceCode.trim().length >= 6;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <div className="text-center space-y-2">
        <h2 className="text-xl font-bold">Add Your First Device</h2>
        <p className="text-sm text-muted-foreground">
          Connect your solar inverter or energy monitor to get started.
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="qr" className="gap-2">
            <QrCode className="h-4 w-4" />
            Scan QR Code
          </TabsTrigger>
          <TabsTrigger value="manual" className="gap-2">
            <Keyboard className="h-4 w-4" />
            Enter Code
          </TabsTrigger>
        </TabsList>
        
        <TabsContent value="qr" className="space-y-4 mt-4">
          <div className="relative aspect-square max-w-[250px] mx-auto rounded-lg border-2 border-dashed border-muted-foreground/30 flex items-center justify-center bg-muted/30">
            {isScanning ? (
              <div className="text-center space-y-3">
                <div className="animate-pulse">
                  <Camera className="h-12 w-12 mx-auto text-primary" />
                </div>
                <p className="text-sm text-muted-foreground">Scanning...</p>
              </div>
            ) : (
              <div className="text-center space-y-3 p-4">
                <QrCode className="h-12 w-12 mx-auto text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  Point your camera at the QR code on your device
                </p>
                <Button onClick={handleQRScan} size="sm">
                  <Camera className="h-4 w-4 mr-2" />
                  Start Scanning
                </Button>
              </div>
            )}
          </div>
          
          {cameraError && (
            <p className="text-sm text-destructive text-center">{cameraError}</p>
          )}
        </TabsContent>
        
        <TabsContent value="manual" className="space-y-4 mt-4">
          <div className="space-y-2">
            <Label htmlFor="deviceCode">Activation Code</Label>
            <Input
              id="deviceCode"
              placeholder="e.g., SM-2024-XXXX-XXXX"
              value={data.deviceCode}
              onChange={(e) => updateData({ deviceCode: e.target.value.toUpperCase() })}
              className="font-mono text-center text-lg tracking-wider"
            />
          </div>
        </TabsContent>
      </Tabs>

      {/* Visual guide */}
      <div className="bg-muted/50 rounded-lg p-4 flex gap-3">
        <Info className="h-5 w-5 text-primary shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="text-sm font-medium">Where to find the code?</p>
          <p className="text-xs text-muted-foreground">
            Look for a sticker on the side or back of your inverter/monitor. The activation code is usually a 12-character alphanumeric code starting with "SM-".
          </p>
        </div>
      </div>

      {data.deviceCode && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-primary/10 rounded-lg p-3 text-center"
        >
          <p className="text-sm font-medium text-primary">Device Code Captured</p>
          <p className="font-mono text-lg">{data.deviceCode}</p>
        </motion.div>
      )}

      <div className="flex justify-between pt-4">
        <Button variant="outline" onClick={prevStep}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Button onClick={nextStep} disabled={!isValid}>
          Test Connection
          <ArrowRight className="h-4 w-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
};

export default DeviceStep;
