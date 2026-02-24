import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  Save,
  Loader2,
  Building2,
  Zap,
  AlertCircle,
  Info,
} from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { useBillingConfig } from "@/hooks/use-billing-config";
import { sitesService } from "@/api/services/sites.service";

const BillingSettingsPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const urlSiteId = searchParams.get("site_id");
  const [siteId, setSiteId] = useState<string>(urlSiteId || "");
  const [isLoadingSite, setIsLoadingSite] = useState(!urlSiteId);
  const [isSaving, setIsSaving] = useState(false);

  // Site metadata for provider schedule detection
  const [siteDiscoProvider, setSiteDiscoProvider] = useState<string | null>(null);
  const [siteTariffCategory, setSiteTariffCategory] = useState<string | null>(null);
  const [isFetchingSiteMeta, setIsFetchingSiteMeta] = useState(false);

  const { config, setConfig, loadFromBackend, saveToBackend, isSyncing } = useBillingConfig();

  // Does the site have a disco provider + tariff category assigned?
  // If yes, rates are managed by admin provider schedule.
  const hasProviderSchedule = !!(siteDiscoProvider && siteTariffCategory);

  // Auto-fetch site ID if not in URL
  useEffect(() => {
    const fetchSiteId = async () => {
      if (urlSiteId) {
        setSiteId(urlSiteId);
        setIsLoadingSite(false);
        return;
      }
      try {
        const result = await sitesService.listSites();
        if (result?.items?.length > 0) {
          const firstId = result.items[0].id;
          setSiteId(firstId);
          navigate(`/billing/settings?site_id=${firstId}`, { replace: true });
        } else {
          toast({ title: "No Sites Found", description: "Create a site first.", variant: "destructive" });
        }
      } catch {
        toast({ title: "Error", description: "Failed to load site information.", variant: "destructive" });
      } finally {
        setIsLoadingSite(false);
      }
    };
    fetchSiteId();
  }, [urlSiteId, navigate]);

  // Load billing config from backend once we have siteId
  useEffect(() => {
    if (siteId && !isLoadingSite) {
      loadFromBackend(siteId);
    }
  }, [siteId, loadFromBackend, isLoadingSite]);

  // Fetch site metadata to check if provider schedule applies
  useEffect(() => {
    if (!siteId || isLoadingSite) return;
    setIsFetchingSiteMeta(true);
    sitesService.getSite(siteId)
      .then((site: any) => {
        const config = site?.configuration ?? site;
        setSiteDiscoProvider(config?.disco_provider ?? config?.discoProvider ?? null);
        setSiteTariffCategory(config?.tariff_category ?? config?.tariffCategory ?? null);
      })
      .catch(() => {
        // Site meta not critical — just means we show full form
      })
      .finally(() => setIsFetchingSiteMeta(false));
  }, [siteId, isLoadingSite]);

  const handleSave = async () => {
    if (!siteId) {
      toast({ title: "No Site Selected", variant: "destructive" });
      return;
    }
    setIsSaving(true);
    try {
      await saveToBackend(siteId);
      toast({ title: "Configuration Saved", description: "Billing settings have been saved." });
      navigate(`/billing?site_id=${siteId}`);
    } catch {
      toast({ title: "Save Failed", description: "Please try again.", variant: "destructive" });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoadingSite) {
    return (
      <AppLayout>
        <AppHeader title="Billing Settings" subtitle="Loading..." />
        <div className="p-6 flex items-center justify-center min-h-[400px]">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </AppLayout>
    );
  }

  if (!siteId) {
    return (
      <AppLayout>
        <AppHeader title="Billing Settings" subtitle="No site available" />
        <div className="p-6">
          <div className="glass-card p-6 text-center">
            <p className="text-muted-foreground mb-4">No site found. Please create a site first.</p>
            <Button onClick={() => navigate("/devices")}>Go to Devices</Button>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <AppHeader
        title="Billing Settings"
        subtitle="Review your tariff rates and set your billing anchor day"
      />

      <div className="p-6 space-y-6 max-w-2xl">
        {/* Back */}
        <Button variant="ghost" size="sm" onClick={() => navigate("/billing")} className="gap-2">
          <ArrowLeft className="w-4 h-4" />
          Back to Billing
        </Button>

        {/* ── Section 1: Provider Info ── */}
        <div className="glass-card p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-primary" />
            <h2 className="font-semibold text-foreground">Provider</h2>
          </div>

          {isFetchingSiteMeta ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading provider info…
            </div>
          ) : hasProviderSchedule ? (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wide">DISCO Provider</p>
                <Badge variant="outline" className="mt-1">{siteDiscoProvider}</Badge>
              </div>
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wide">Tariff Category</p>
                <Badge variant="outline" className="mt-1">{siteTariffCategory}</Badge>
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800">
              <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
              <p className="text-sm text-amber-800 dark:text-amber-200">
                No DISCO provider or tariff category assigned to this site. Rates below come from
                your manual configuration. Contact your administrator to assign a provider schedule.
              </p>
            </div>
          )}
        </div>

        {/* ── Section 2: Effective Rates (read-only) ── */}
        <div className="glass-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary" />
              <h2 className="font-semibold text-foreground">Effective Rates</h2>
            </div>
            {hasProviderSchedule && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Info className="w-3 h-3" />
                Managed by admin
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="p-3 rounded-lg bg-secondary/40 space-y-1">
              <p className="text-xs text-muted-foreground">Off-peak Import</p>
              <p className="font-semibold">₨{config.offPeakPrice.toFixed(4)}/kWh</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary/40 space-y-1">
              <p className="text-xs text-muted-foreground">Peak Import</p>
              <p className="font-semibold">₨{config.peakPrice.toFixed(4)}/kWh</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary/40 space-y-1">
              <p className="text-xs text-muted-foreground">Off-peak Settlement</p>
              <p className="font-semibold">₨{config.offPeakSettlement.toFixed(4)}/kWh</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary/40 space-y-1">
              <p className="text-xs text-muted-foreground">Peak Settlement</p>
              <p className="font-semibold">₨{config.peakSettlement.toFixed(4)}/kWh</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="p-3 rounded-lg bg-secondary/40 space-y-1">
              <p className="text-xs text-muted-foreground">Fixed Monthly Charge</p>
              <p className="font-semibold">₨{config.fixedCharge.toFixed(2)}</p>
            </div>
            <div className="p-3 rounded-lg bg-secondary/40 space-y-1">
              <p className="text-xs text-muted-foreground">Peak Windows</p>
              <p className="font-semibold text-sm">
                {config.peakWindows.map((w) => `${w.start}–${w.end}`).join(", ")}
              </p>
            </div>
          </div>

          {!hasProviderSchedule && (
            <p className="text-xs text-muted-foreground">
              These rates come from your manual billing configuration. An admin can assign a
              provider schedule to manage rates centrally.
            </p>
          )}
        </div>

        {/* ── Section 3: Anchor Day (editable) ── */}
        <div className="glass-card p-5 space-y-4">
          <h2 className="font-semibold text-foreground">Billing Anchor Day</h2>
          <p className="text-sm text-muted-foreground">
            Your billing cycle starts on this day of each month. For example, if set to 15, your
            bill covers the 15th of each month to the 14th of the next.
          </p>

          <div className="flex items-center gap-4 max-w-xs">
            <Label className="w-24 shrink-0">Anchor Day</Label>
            <Input
              type="number"
              min={1}
              max={28}
              value={config.anchorDay}
              onChange={(e) => setConfig((c) => ({ ...c, anchorDay: Number(e.target.value) }))}
              className="w-24"
            />
            <span className="text-sm text-muted-foreground">of each month</span>
          </div>
        </div>

        {/* ── Save ── */}
        <div className="flex gap-3">
          <Button onClick={handleSave} disabled={isSaving || isSyncing} className="gap-2">
            {(isSaving || isSyncing) ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Save Anchor Day
          </Button>
          <Button variant="outline" onClick={() => navigate("/billing")} disabled={isSaving}>
            Cancel
          </Button>
        </div>
      </div>
    </AppLayout>
  );
};

export default BillingSettingsPage;
