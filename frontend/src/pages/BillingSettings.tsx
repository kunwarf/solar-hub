import { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Globe,
  Zap,
  Calculator,
  CheckCircle,
  ArrowLeft,
  ArrowRight,
  Save,
  RotateCcw,
  Clock,
  Plus,
  Trash2,
  DollarSign,
  TrendingUp,
  LayoutDashboard,
} from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { useBillingConfig, defaultConfig, type PeakWindow } from "@/hooks/use-billing-config";

const BillingSettingsPage = () => {
  const navigate = useNavigate();
  const { config, setConfig } = useBillingConfig();
  const [isFirstTime, setIsFirstTime] = useState(false); // Set to true for first-time wizard
  const [currentStep, setCurrentStep] = useState(1);

  const steps = [
    { number: 1, title: "Global Settings", icon: Globe },
    { number: 2, title: "Tariff & Net-Metering", icon: Zap },
    { number: 3, title: "Fixed Charges & Forecast", icon: Calculator },
    { number: 4, title: "Review & Save", icon: CheckCircle },
  ];

  const handleAddPeakWindow = () => {
    const newWindow: PeakWindow = {
      id: Date.now().toString(),
      start: "09:00",
      end: "17:00",
    };
    setConfig({ ...config, peakWindows: [...config.peakWindows, newWindow] });
  };

  const handleRemovePeakWindow = (id: string) => {
    setConfig({
      ...config,
      peakWindows: config.peakWindows.filter((w) => w.id !== id),
    });
  };

  const handleUpdatePeakWindow = (id: string, field: "start" | "end", value: string) => {
    setConfig({
      ...config,
      peakWindows: config.peakWindows.map((w) =>
        w.id === id ? { ...w, [field]: value } : w
      ),
    });
  };

  const handleSave = () => {
    toast({
      title: "Configuration Saved",
      description: "Billing settings have been updated successfully.",
    });
    setIsFirstTime(false);
    navigate("/billing");
  };

  const handleReset = () => {
    setConfig(defaultConfig);
    toast({
      title: "Settings Reset",
      description: "Billing configuration restored to defaults.",
    });
  };

  const renderStepIndicator = () => (
    <div className="flex items-center justify-center gap-2 mb-8">
      {steps.map((step, index) => (
        <div key={step.number} className="flex items-center">
          <button
            onClick={() => setCurrentStep(step.number)}
            className={cn(
              "w-10 h-10 rounded-full flex items-center justify-center font-medium transition-all",
              currentStep === step.number
                ? "bg-primary text-primary-foreground"
                : currentStep > step.number
                ? "bg-green-500 text-white"
                : "bg-secondary text-muted-foreground"
            )}
          >
            {currentStep > step.number ? (
              <CheckCircle className="w-5 h-5" />
            ) : (
              step.number
            )}
          </button>
          {index < steps.length - 1 && (
            <div
              className={cn(
                "w-12 h-0.5 mx-1",
                currentStep > step.number ? "bg-green-500" : "bg-secondary"
              )}
            />
          )}
        </div>
      ))}
    </div>
  );

  const renderGlobalSettings = () => (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-foreground">1. Global Billing Settings</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-2">
          <Label>Currency</Label>
          <Select
            value={config.currency}
            onValueChange={(value) => setConfig({ ...config, currency: value })}
          >
            <SelectTrigger className="bg-secondary/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="PKR">PKR (₨)</SelectItem>
              <SelectItem value="USD">USD ($)</SelectItem>
              <SelectItem value="EUR">EUR (€)</SelectItem>
              <SelectItem value="GBP">GBP (£)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Billing Anchor Day (1-28)</Label>
          <Input
            type="number"
            min={1}
            max={28}
            value={config.anchorDay}
            onChange={(e) => setConfig({ ...config, anchorDay: Number(e.target.value) })}
            className="bg-secondary/50"
          />
          <p className="text-xs text-muted-foreground">Your billing cycle starts on this day of each month</p>
        </div>
      </div>
    </div>
  );

  const renderTariffSettings = () => (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-foreground">2. Tariff & Net-Metering</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-2">
          <Label>Off-peak price (per kWh)</Label>
          <Input
            type="number"
            value={config.offPeakPrice}
            onChange={(e) => setConfig({ ...config, offPeakPrice: Number(e.target.value) })}
            className="bg-secondary/50"
          />
        </div>

        <div className="space-y-2">
          <Label>Peak price (per kWh)</Label>
          <Input
            type="number"
            value={config.peakPrice}
            onChange={(e) => setConfig({ ...config, peakPrice: Number(e.target.value) })}
            className="bg-secondary/50"
          />
        </div>

        <div className="space-y-2">
          <Label>Off-peak settlement price</Label>
          <Input
            type="number"
            value={config.offPeakSettlement}
            onChange={(e) => setConfig({ ...config, offPeakSettlement: Number(e.target.value) })}
            className="bg-secondary/50"
          />
          <p className="text-xs text-muted-foreground">Price paid for excess export credits at cycle end</p>
        </div>

        <div className="space-y-2">
          <Label>Peak settlement price</Label>
          <Input
            type="number"
            value={config.peakSettlement}
            onChange={(e) => setConfig({ ...config, peakSettlement: Number(e.target.value) })}
            className="bg-secondary/50"
          />
          <p className="text-xs text-muted-foreground">Price paid for excess peak export credits at cycle end</p>
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Label>Peak Time Windows</Label>
          <Button variant="outline" size="sm" onClick={handleAddPeakWindow} className="gap-2">
            <Plus className="w-4 h-4" />
            Add Window
          </Button>
        </div>
        <div className="space-y-3">
          {config.peakWindows.map((window) => (
            <div key={window.id} className="flex items-center gap-3 p-3 rounded-lg bg-secondary/30">
              <Input
                type="time"
                value={window.start}
                onChange={(e) => handleUpdatePeakWindow(window.id, "start", e.target.value)}
                className="bg-secondary/50 w-32"
              />
              <span className="text-muted-foreground">to</span>
              <Input
                type="time"
                value={window.end}
                onChange={(e) => handleUpdatePeakWindow(window.id, "end", e.target.value)}
                className="bg-secondary/50 w-32"
              />
              {config.peakWindows.length > 1 && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleRemovePeakWindow(window.id)}
                  className="text-destructive hover:text-destructive"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderForecastSettings = () => (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-foreground">3. Fixed Charges & Forecast</h3>
      <div className="space-y-2">
        <Label>Fixed charge per billing month</Label>
        <Input
          type="number"
          value={config.fixedCharge}
          onChange={(e) => setConfig({ ...config, fixedCharge: Number(e.target.value) })}
          className="bg-secondary/50"
        />
        <p className="text-xs text-muted-foreground">Meter rent, service fee, etc.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="space-y-2">
          <Label>Forecast method</Label>
          <Select
            value={config.forecastMethod}
            onValueChange={(value) => setConfig({ ...config, forecastMethod: value })}
          >
            <SelectTrigger className="bg-secondary/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="trend">Trend-based</SelectItem>
              <SelectItem value="average">Simple Average</SelectItem>
              <SelectItem value="seasonal">Seasonal</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Look-back months</Label>
          <Input
            type="number"
            value={config.lookbackMonths}
            onChange={(e) => setConfig({ ...config, lookbackMonths: Number(e.target.value) })}
            className="bg-secondary/50"
          />
        </div>

        <div className="space-y-2">
          <Label>Default months ahead</Label>
          <Input
            type="number"
            value={config.defaultMonthsAhead}
            onChange={(e) => setConfig({ ...config, defaultMonthsAhead: Number(e.target.value) })}
            className="bg-secondary/50"
          />
        </div>
      </div>
    </div>
  );

  const renderReviewScreen = () => (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-foreground">4. Review & Save</h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Billing Cycle */}
        <div className="p-4 rounded-lg bg-secondary/30 space-y-3">
          <div className="flex items-center gap-2">
            <Globe className="w-5 h-5 text-primary" />
            <span className="font-medium text-foreground">Billing Cycle</span>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Currency</span>
              <span className="text-foreground font-medium">{config.currency}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Anchor Day</span>
              <span className="text-foreground font-medium">{config.anchorDay}th of each month</span>
            </div>
          </div>
        </div>

        {/* Tariff Rates */}
        <div className="p-4 rounded-lg bg-secondary/30 space-y-3">
          <div className="flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-primary" />
            <span className="font-medium text-foreground">Tariff Rates</span>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Off-peak</span>
              <span className="text-foreground font-medium">{config.currency} {config.offPeakPrice}/kWh</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Peak</span>
              <span className="text-foreground font-medium">{config.currency} {config.peakPrice}/kWh</span>
            </div>
          </div>
        </div>

        {/* Settlement Rates */}
        <div className="p-4 rounded-lg bg-secondary/30 space-y-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-primary" />
            <span className="font-medium text-foreground">Settlement Rates</span>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Off-peak Export</span>
              <span className="text-foreground font-medium">{config.currency} {config.offPeakSettlement}/kWh</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Peak Export</span>
              <span className="text-foreground font-medium">{config.currency} {config.peakSettlement}/kWh</span>
            </div>
          </div>
        </div>

        {/* Peak Windows */}
        <div className="p-4 rounded-lg bg-secondary/30 space-y-3">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-primary" />
            <span className="font-medium text-foreground">Peak Hours</span>
          </div>
          <div className="space-y-2">
            {config.peakWindows.map((window, index) => (
              <Badge key={window.id} variant="outline" className="mr-2">
                {window.start} - {window.end}
              </Badge>
            ))}
          </div>
        </div>

        {/* Fixed Charges */}
        <div className="p-4 rounded-lg bg-secondary/30 space-y-3">
          <div className="flex items-center gap-2">
            <Calculator className="w-5 h-5 text-primary" />
            <span className="font-medium text-foreground">Fixed Charges</span>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Monthly Fixed</span>
              <span className="text-foreground font-medium">{config.currency} {config.fixedCharge}</span>
            </div>
          </div>
        </div>

        {/* Forecast Settings */}
        <div className="p-4 rounded-lg bg-secondary/30 space-y-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-primary" />
            <span className="font-medium text-foreground">Forecast</span>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Method</span>
              <span className="text-foreground font-medium capitalize">{config.forecastMethod}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Look-back</span>
              <span className="text-foreground font-medium">{config.lookbackMonths} months</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderWizard = () => (
    <div className="space-y-6">
      {renderStepIndicator()}

      <motion.div
        key={currentStep}
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        className="glass-card p-6"
      >
        {currentStep === 1 && renderGlobalSettings()}
        {currentStep === 2 && renderTariffSettings()}
        {currentStep === 3 && renderForecastSettings()}
        {currentStep === 4 && renderReviewScreen()}
      </motion.div>

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => setCurrentStep(Math.max(1, currentStep - 1))}
          disabled={currentStep === 1}
          className="gap-2"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Button>
        
        {currentStep < 4 ? (
          <Button onClick={() => setCurrentStep(currentStep + 1)} className="gap-2">
            Next
            <ArrowRight className="w-4 h-4" />
          </Button>
        ) : (
          <Button onClick={handleSave} className="gap-2">
            <Save className="w-4 h-4" />
            Save Configuration
          </Button>
        )}
      </div>
    </div>
  );

  const renderAccordion = () => (
    <div className="space-y-4">
      <Accordion type="multiple" defaultValue={["global", "tariff", "forecast"]} className="space-y-4">
        <AccordionItem value="global" className="glass-card border-0">
          <AccordionTrigger className="px-6 py-4 hover:no-underline">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Globe className="w-5 h-5 text-primary" />
              </div>
              <div className="text-left">
                <p className="font-medium text-foreground">Global Billing Settings</p>
                <p className="text-sm text-muted-foreground">Currency and billing cycle configuration</p>
              </div>
            </div>
          </AccordionTrigger>
          <AccordionContent className="px-6 pb-6">
            <div className="pt-4">{renderGlobalSettings()}</div>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="tariff" className="glass-card border-0">
          <AccordionTrigger className="px-6 py-4 hover:no-underline">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Zap className="w-5 h-5 text-primary" />
              </div>
              <div className="text-left">
                <p className="font-medium text-foreground">Tariff & Net-Metering</p>
                <p className="text-sm text-muted-foreground">Pricing, settlement rates, and peak hours</p>
              </div>
            </div>
          </AccordionTrigger>
          <AccordionContent className="px-6 pb-6">
            <div className="pt-4">{renderTariffSettings()}</div>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="forecast" className="glass-card border-0">
          <AccordionTrigger className="px-6 py-4 hover:no-underline">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Calculator className="w-5 h-5 text-primary" />
              </div>
              <div className="text-left">
                <p className="font-medium text-foreground">Fixed Charges & Forecast</p>
                <p className="text-sm text-muted-foreground">Monthly fees and forecasting configuration</p>
              </div>
            </div>
          </AccordionTrigger>
          <AccordionContent className="px-6 pb-6">
            <div className="pt-4">{renderForecastSettings()}</div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      {/* Summary Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-6"
      >
        {renderReviewScreen()}
      </motion.div>

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-4">
        <Button onClick={handleSave} className="gap-2">
          <Save className="w-4 h-4" />
          Save Changes
        </Button>
        <Button variant="outline" onClick={handleReset} className="gap-2">
          <RotateCcw className="w-4 h-4" />
          Reset to Defaults
        </Button>
      </div>
    </div>
  );

  return (
    <AppLayout>
      <AppHeader
        title="Billing Setup"
        subtitle="Configure billing cycle, tariffs, net-metering and forecasting"
      />

      <div className="p-6 space-y-6">
        {/* Top Actions */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate("/billing")} className="gap-2">
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </Button>
          
          {!isFirstTime && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsFirstTime(true)}
              className="gap-2"
            >
              <LayoutDashboard className="w-4 h-4" />
              Switch to Wizard View
            </Button>
          )}
          
          {isFirstTime && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsFirstTime(false)}
              className="gap-2"
            >
              <LayoutDashboard className="w-4 h-4" />
              Switch to Accordion View
            </Button>
          )}
        </div>

        {isFirstTime ? renderWizard() : renderAccordion()}
      </div>
    </AppLayout>
  );
};

export default BillingSettingsPage;
