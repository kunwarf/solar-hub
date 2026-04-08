/**
 * MQTTIntegrationCard
 *
 * Lets users set up and manage their Home Assistant MQTT integration.
 * Handles the full lifecycle: create, view credentials, rotate password,
 * enroll/unenroll devices, and delete.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Plug,
  Copy,
  Eye,
  EyeOff,
  RefreshCw,
  Trash2,
  CheckCircle,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { toast } from "@/hooks/use-toast";
import integrationsService from "@/api/services/integrations.service";
import type {
  MqttIntegrationResponse,
  DeviceEnrollmentItem,
} from "@/api/services/integrations.service";

// -------------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------------

function copyToClipboard(text: string, label: string) {
  navigator.clipboard.writeText(text).then(() => {
    toast({ title: `${label} copied to clipboard` });
  });
}

// -------------------------------------------------------------------------
// Sub-components
// -------------------------------------------------------------------------

interface CredentialRowProps {
  label: string;
  value: string;
  secret?: boolean;
}

function CredentialRow({ label, value, secret = false }: CredentialRowProps) {
  const [visible, setVisible] = useState(!secret);

  return (
    <div className="flex items-center justify-between py-2 border-b border-white/10 last:border-0">
      <span className="text-sm text-muted-foreground w-32 shrink-0">{label}</span>
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <code className="text-sm font-mono bg-black/20 rounded px-2 py-0.5 flex-1 truncate">
          {visible ? value : "••••••••••••••••"}
        </code>
        {secret && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0"
            onClick={() => setVisible((v) => !v)}
          >
            {visible ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={() => copyToClipboard(value, label)}
        >
          <Copy className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
}

// -------------------------------------------------------------------------
// Main component
// -------------------------------------------------------------------------

export function MQTTIntegrationCard() {
  const queryClient = useQueryClient();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [newPassword, setNewPassword] = useState<string | null>(null);

  // Fetch existing integration (404 → null)
  const { data: integration, isLoading } = useQuery<MqttIntegrationResponse | null>({
    queryKey: ["mqtt-integration"],
    queryFn: async () => {
      try {
        return await integrationsService.getMqttIntegration();
      } catch (err: any) {
        if (err?.response?.status === 404) return null;
        throw err;
      }
    },
    retry: false,
  });

  // Fetch device list when integration exists
  const { data: devices = [] } = useQuery<DeviceEnrollmentItem[]>({
    queryKey: ["mqtt-devices"],
    queryFn: () => integrationsService.listMqttDevices(),
    enabled: !!integration,
  });

  // Create integration
  const createMutation = useMutation({
    mutationFn: () => integrationsService.createMqttIntegration(),
    onSuccess: (data) => {
      setNewPassword(data.password);
      queryClient.invalidateQueries({ queryKey: ["mqtt-integration"] });
      toast({ title: "Integration created", description: "Save your password now." });
    },
    onError: (err: any) => {
      toast({
        title: "Failed to create integration",
        description: err?.response?.data?.detail ?? "Unknown error",
        variant: "destructive",
      });
    },
  });

  // Rotate password
  const rotateMutation = useMutation({
    mutationFn: () => integrationsService.rotateMqttPassword(),
    onSuccess: (data) => {
      setNewPassword(data.password);
      toast({ title: "Password regenerated", description: "Save your new password now." });
    },
    onError: (err: any) => {
      toast({
        title: "Failed to rotate password",
        description: err?.response?.data?.detail ?? "Unknown error",
        variant: "destructive",
      });
    },
  });

  // Delete integration
  const deleteMutation = useMutation({
    mutationFn: () => integrationsService.deleteMqttIntegration(),
    onSuccess: () => {
      setShowDeleteConfirm(false);
      setNewPassword(null);
      queryClient.invalidateQueries({ queryKey: ["mqtt-integration"] });
      queryClient.invalidateQueries({ queryKey: ["mqtt-devices"] });
      toast({ title: "Integration deleted" });
    },
    onError: (err: any) => {
      toast({
        title: "Failed to delete integration",
        description: err?.response?.data?.detail ?? "Unknown error",
        variant: "destructive",
      });
    },
  });

  // Enroll / unenroll device
  const enrollMutation = useMutation({
    mutationFn: ({ deviceId, enrolled }: { deviceId: string; enrolled: boolean }) =>
      integrationsService.setDeviceEnrollment(deviceId, enrolled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mqtt-devices"] });
    },
    onError: (err: any) => {
      toast({
        title: "Failed to update enrollment",
        description: err?.response?.data?.detail ?? "Unknown error",
        variant: "destructive",
      });
    },
  });

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  if (isLoading) {
    return (
      <div className="glass-card p-6 flex items-center gap-3">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        <span className="text-muted-foreground">Loading integration status…</span>
      </div>
    );
  }

  // No integration yet
  if (!integration) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-6 space-y-4"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-500/20">
            <Plug className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h3 className="font-semibold">Home Assistant Integration</h3>
            <p className="text-sm text-muted-foreground">
              Connect your Solar Hub devices to Home Assistant via MQTT
            </p>
          </div>
        </div>

        <p className="text-sm text-muted-foreground">
          Enable this integration to automatically publish real-time solar data to your
          Home Assistant instance. No YAML configuration needed — HA auto-discovers all
          enrolled devices.
        </p>

        <Button
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending}
          className="gap-2"
        >
          {createMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Plug className="w-4 h-4" />
          )}
          Enable Home Assistant Integration
        </Button>
      </motion.div>
    );
  }

  // Integration exists — show management UI
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      {/* Header */}
      <div className="glass-card p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-green-500/20">
            <Plug className="w-5 h-5 text-green-400" />
          </div>
          <div>
            <h3 className="font-semibold">Home Assistant Integration</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <CheckCircle className="w-3.5 h-3.5 text-green-400" />
              <span className="text-sm text-green-400">Active</span>
            </div>
          </div>
        </div>
        <Badge variant="secondary" className="text-xs">
          {devices.filter((d) => d.enrolled).length}/{devices.length} devices enrolled
        </Badge>
      </div>

      {/* New password banner (shown once after creation or rotation) */}
      {newPassword && (
        <div className="glass-card p-4 border border-yellow-500/30 bg-yellow-500/5 space-y-2">
          <div className="flex items-center gap-2 text-yellow-400">
            <AlertCircle className="w-4 h-4" />
            <span className="text-sm font-medium">Save this password — it won't be shown again</span>
          </div>
          <CredentialRow label="Password" value={newPassword} secret />
          <Button
            variant="ghost"
            size="sm"
            className="text-xs"
            onClick={() => setNewPassword(null)}
          >
            I've saved it
          </Button>
        </div>
      )}

      {/* Broker credentials */}
      <div className="glass-card p-4 space-y-1">
        <h4 className="text-sm font-medium mb-3">Broker Credentials</h4>
        <CredentialRow label="Host" value={integration.broker_host} />
        <CredentialRow label="Port" value={String(integration.broker_port)} />
        <CredentialRow label="Username" value={integration.ha_username} />
        <div className="flex items-center justify-between pt-3">
          <span className="text-xs text-muted-foreground">Password</span>
          <Button
            variant="outline"
            size="sm"
            className="gap-2 text-xs"
            onClick={() => rotateMutation.mutate()}
            disabled={rotateMutation.isPending}
          >
            {rotateMutation.isPending ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <RefreshCw className="w-3 h-3" />
            )}
            Regenerate
          </Button>
        </div>
      </div>

      {/* Device enrollment */}
      <div className="glass-card p-4 space-y-3">
        <h4 className="text-sm font-medium">Enrolled Devices</h4>
        {devices.length === 0 ? (
          <p className="text-sm text-muted-foreground">No devices found.</p>
        ) : (
          <div className="space-y-2">
            {devices.map((device) => (
              <div
                key={device.device_id}
                className="flex items-center justify-between py-2 border-b border-white/10 last:border-0"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{device.name}</p>
                  <p className="text-xs text-muted-foreground">{device.serial_number}</p>
                </div>
                <Switch
                  checked={device.enrolled}
                  disabled={enrollMutation.isPending}
                  onCheckedChange={(enrolled) =>
                    enrollMutation.mutate({ deviceId: device.device_id, enrolled })
                  }
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Setup guide */}
      <Accordion type="single" collapsible>
        <AccordionItem value="setup-guide" className="glass-card border-0">
          <AccordionTrigger className="px-4 text-sm">
            How to connect Home Assistant
          </AccordionTrigger>
          <AccordionContent className="px-4 pb-4 text-sm text-muted-foreground space-y-2">
            <p>1. In Home Assistant, go to <strong>Settings → Devices & Services → Add Integration</strong>.</p>
            <p>2. Search for <strong>MQTT</strong> and add it.</p>
            <p>3. Enter the broker credentials shown above.</p>
            <p>4. Solar Hub devices will appear automatically under <strong>Devices</strong> — no YAML needed.</p>
            <p className="text-xs mt-3 opacity-70">
              Make sure your HA instance can reach <code>{integration.broker_host}:{integration.broker_port}</code>.
              For external access, configure port forwarding or a reverse proxy with TLS.
            </p>
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      {/* Delete */}
      <div className="glass-card p-4">
        {!showDeleteConfirm ? (
          <Button
            variant="ghost"
            size="sm"
            className="text-destructive gap-2"
            onClick={() => setShowDeleteConfirm(true)}
          >
            <Trash2 className="w-4 h-4" />
            Delete Integration
          </Button>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-destructive">
              This will revoke your MQTT credentials and disconnect all enrolled devices from HA.
            </p>
            <div className="flex gap-2">
              <Button
                variant="destructive"
                size="sm"
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
                className="gap-2"
              >
                {deleteMutation.isPending && <Loader2 className="w-3 h-3 animate-spin" />}
                Yes, delete
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowDeleteConfirm(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

export default MQTTIntegrationCard;
