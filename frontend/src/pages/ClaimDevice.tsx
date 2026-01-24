import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Search,
  Cpu,
  CheckCircle,
  AlertCircle,
  Loader2,
  Wifi,
  WifiOff,
  Clock,
  Tag,
  Server,
  ArrowRight,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/hooks/use-auth";
import { devicesService, sitesService } from "@/api";
import type { OrphanDevice, Site } from "@/api/types";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

type LookupState = "idle" | "loading" | "found" | "not_found" | "error";

const ClaimDevicePage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [serialNumber, setSerialNumber] = useState("");
  const [lookupState, setLookupState] = useState<LookupState>("idle");
  const [device, setDevice] = useState<OrphanDevice | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedSiteId, setSelectedSiteId] = useState<string>("");
  const [isClaiming, setIsClaiming] = useState(false);

  // Fetch available sites
  const { data: sitesData, isLoading: sitesLoading } = useQuery({
    queryKey: ["sites"],
    queryFn: async () => {
      const result = await sitesService.listSites();
      return result.items;
    },
  });

  const sites = sitesData || [];

  // Format serial number as user types (add dashes)
  const formatSerialInput = (value: string) => {
    // Remove all non-alphanumeric characters
    const cleaned = value.replace(/[^a-zA-Z0-9]/g, "").toUpperCase();

    // Add dashes every 4 characters
    const parts = cleaned.match(/.{1,4}/g) || [];
    return parts.join("-").slice(0, 19); // Max length: 16 chars + 3 dashes
  };

  const handleSerialChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const formatted = formatSerialInput(e.target.value);
    setSerialNumber(formatted);
    // Reset state when serial changes
    if (lookupState !== "idle" && lookupState !== "loading") {
      setLookupState("idle");
      setDevice(null);
      setError(null);
    }
  };

  const lookupDevice = useCallback(async () => {
    if (!serialNumber || serialNumber.replace(/-/g, "").length < 16) {
      toast.error("Please enter a valid 16-character serial number");
      return;
    }

    setLookupState("loading");
    setError(null);
    setDevice(null);

    try {
      // Remove dashes for API call
      const cleanSerial = serialNumber.replace(/-/g, "");
      const result = await devicesService.getDeviceBySerial(cleanSerial);

      if (result.found && result.device) {
        setDevice(result.device);
        setLookupState("found");

        if (result.device.status === "claimed") {
          setError("This device has already been claimed by another user.");
        }
      } else {
        setLookupState("not_found");
        setError(result.error || "Device not found");
      }
    } catch (err) {
      setLookupState("error");
      setError("Failed to look up device. Please try again.");
    }
  }, [serialNumber]);

  const claimDevice = useCallback(async () => {
    if (!device || !user || !selectedSiteId) {
      toast.error("Please select a site to add the device to");
      return;
    }

    const site = sites.find((s: Site) => s.id === selectedSiteId);
    if (!site) {
      toast.error("Selected site not found");
      return;
    }

    setIsClaiming(true);

    try {
      const result = await devicesService.claimDevice(device.id, {
        owner_id: user.id,
        site_id: selectedSiteId,
        organization_id: site.organization_id,
      });

      if (result.success) {
        toast.success("Device claimed successfully!");
        navigate("/devices");
      } else {
        toast.error(result.message || "Failed to claim device");
      }
    } catch (err) {
      toast.error("Failed to claim device. Please try again.");
    } finally {
      setIsClaiming(false);
    }
  }, [device, user, selectedSiteId, sites, navigate]);

  const getConnectionStatusColor = (status: string) => {
    switch (status) {
      case "connected":
        return "text-success";
      case "disconnected":
        return "text-muted-foreground";
      case "error":
        return "text-destructive";
      default:
        return "text-muted-foreground";
    }
  };

  const getConnectionStatusIcon = (status: string) => {
    switch (status) {
      case "connected":
        return <Wifi className="w-4 h-4" />;
      case "disconnected":
        return <WifiOff className="w-4 h-4" />;
      default:
        return <WifiOff className="w-4 h-4" />;
    }
  };

  return (
    <AppLayout>
      <AppHeader
        title="Claim Device"
        subtitle="Add a new device to your account by entering its serial number"
      />

      <div className="p-6 space-y-6 max-w-2xl mx-auto">
        {/* Serial Number Input */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-6"
        >
          <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <Tag className="w-5 h-5" />
            Device Serial Number
          </h3>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="serial">
                Enter the 16-character serial number from your device
              </Label>
              <div className="flex gap-2">
                <Input
                  id="serial"
                  value={serialNumber}
                  onChange={handleSerialChange}
                  placeholder="SHXX-XXXX-XXXX-XXXX"
                  className="bg-secondary/50 font-mono text-lg tracking-wider"
                  maxLength={19}
                />
                <Button
                  onClick={lookupDevice}
                  disabled={lookupState === "loading" || serialNumber.replace(/-/g, "").length < 16}
                >
                  {lookupState === "loading" ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Search className="w-4 h-4" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                The serial number is printed on your device label. Format: SH01-IN9A-423V-4CU0
              </p>
            </div>
          </div>
        </motion.div>

        {/* Device Status - Not Found */}
        {lookupState === "not_found" && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-6 border-amber-500/30"
          >
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-full bg-amber-500/20">
                <AlertCircle className="w-6 h-6 text-amber-500" />
              </div>
              <div className="flex-1">
                <h4 className="font-semibold text-foreground mb-1">Device Not Found</h4>
                <p className="text-sm text-muted-foreground mb-4">
                  {error || "We couldn't find a device with this serial number."}
                </p>
                <div className="text-sm text-muted-foreground space-y-2">
                  <p className="font-medium">Troubleshooting steps:</p>
                  <ul className="list-disc list-inside space-y-1 ml-2">
                    <li>Ensure your device is powered on and connected to WiFi</li>
                    <li>Wait a few moments for the device to register with our servers</li>
                    <li>Double-check the serial number on your device label</li>
                    <li>Try the lookup again after the device has connected</li>
                  </ul>
                </div>
                <Button
                  variant="outline"
                  className="mt-4 gap-2"
                  onClick={lookupDevice}
                >
                  <RefreshCw className="w-4 h-4" />
                  Try Again
                </Button>
              </div>
            </div>
          </motion.div>
        )}

        {/* Device Status - Error */}
        {lookupState === "error" && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-6 border-destructive/30"
          >
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-full bg-destructive/20">
                <AlertCircle className="w-6 h-6 text-destructive" />
              </div>
              <div className="flex-1">
                <h4 className="font-semibold text-foreground mb-1">Lookup Failed</h4>
                <p className="text-sm text-muted-foreground">
                  {error || "Something went wrong. Please try again."}
                </p>
                <Button
                  variant="outline"
                  className="mt-4 gap-2"
                  onClick={lookupDevice}
                >
                  <RefreshCw className="w-4 h-4" />
                  Retry
                </Button>
              </div>
            </div>
          </motion.div>
        )}

        {/* Device Found */}
        {lookupState === "found" && device && (
          <>
            {/* Device Info Card */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-6 border-success/30"
            >
              <div className="flex items-start gap-4">
                <div className="p-3 rounded-full bg-success/20">
                  <CheckCircle className="w-6 h-6 text-success" />
                </div>
                <div className="flex-1">
                  <h4 className="font-semibold text-foreground mb-1">Device Found</h4>
                  <p className="text-sm text-muted-foreground">
                    {device.status === "claimed"
                      ? "This device has already been claimed."
                      : "This device is available to claim."
                    }
                  </p>
                </div>
              </div>

              {/* Device Details */}
              <div className="mt-6 grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Serial Number</p>
                  <p className="font-mono text-sm text-foreground">{device.serial_number}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Device Type</p>
                  <p className="text-sm text-foreground capitalize flex items-center gap-2">
                    <Cpu className="w-4 h-4" />
                    {device.device_type}
                  </p>
                </div>
                {device.manufacturer && (
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Manufacturer</p>
                    <p className="text-sm text-foreground">{device.manufacturer}</p>
                  </div>
                )}
                {device.model && (
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Model</p>
                    <p className="text-sm text-foreground">{device.model}</p>
                  </div>
                )}
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Connection Status</p>
                  <p className={`text-sm flex items-center gap-2 ${getConnectionStatusColor(device.connection_status)}`}>
                    {getConnectionStatusIcon(device.connection_status)}
                    <span className="capitalize">{device.connection_status}</span>
                  </p>
                </div>
                {device.firmware_version && (
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Firmware</p>
                    <p className="text-sm text-foreground flex items-center gap-2">
                      <Server className="w-4 h-4" />
                      v{device.firmware_version}
                    </p>
                  </div>
                )}
                {device.last_connected_at && (
                  <div className="space-y-1 col-span-2">
                    <p className="text-xs text-muted-foreground">Last Connected</p>
                    <p className="text-sm text-foreground flex items-center gap-2">
                      <Clock className="w-4 h-4" />
                      {new Date(device.last_connected_at).toLocaleString()}
                    </p>
                  </div>
                )}
              </div>
            </motion.div>

            {/* Claim Form - Only show if device is unclaimed */}
            {device.status !== "claimed" && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="glass-card p-6"
              >
                <h3 className="text-lg font-semibold text-foreground mb-4">
                  Add to Your Account
                </h3>

                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="site">Select Site</Label>
                    <Select value={selectedSiteId} onValueChange={setSelectedSiteId}>
                      <SelectTrigger className="bg-secondary/50">
                        <SelectValue placeholder="Choose a site for this device" />
                      </SelectTrigger>
                      <SelectContent>
                        {sitesLoading ? (
                          <SelectItem value="loading" disabled>Loading sites...</SelectItem>
                        ) : sites.length === 0 ? (
                          <SelectItem value="none" disabled>No sites available</SelectItem>
                        ) : (
                          sites.map((site: Site) => (
                            <SelectItem key={site.id} value={site.id}>
                              {site.name}
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      The device will be added to the selected site for monitoring and management.
                    </p>
                  </div>

                  <Button
                    className="w-full gap-2"
                    size="lg"
                    onClick={claimDevice}
                    disabled={!selectedSiteId || isClaiming}
                  >
                    {isClaiming ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Claiming Device...
                      </>
                    ) : (
                      <>
                        Claim Device
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </Button>
                </div>
              </motion.div>
            )}

            {/* Already Claimed Warning */}
            {device.status === "claimed" && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="glass-card p-6 border-amber-500/30"
              >
                <div className="flex items-start gap-4">
                  <div className="p-3 rounded-full bg-amber-500/20">
                    <AlertCircle className="w-6 h-6 text-amber-500" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-foreground mb-1">Device Already Claimed</h4>
                    <p className="text-sm text-muted-foreground">
                      This device has already been claimed by another user. If you believe this is an error,
                      please contact support.
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </>
        )}

        {/* Help Section */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-card p-6"
        >
          <h3 className="text-lg font-semibold text-foreground mb-4">
            Need Help?
          </h3>
          <div className="text-sm text-muted-foreground space-y-3">
            <p>
              <strong>Where is my serial number?</strong><br />
              The serial number is printed on a label on your SolarHub data logger device.
              It starts with "SH" and is 16 characters long.
            </p>
            <p>
              <strong>Device not showing up?</strong><br />
              Make sure your device is powered on and connected to WiFi. It may take a few
              moments for new devices to register with our servers.
            </p>
            <p>
              <strong>Still having issues?</strong><br />
              Contact our support team for assistance with device registration.
            </p>
          </div>
        </motion.div>
      </div>
    </AppLayout>
  );
};

export default ClaimDevicePage;
