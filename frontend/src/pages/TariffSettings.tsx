import { useState } from 'react';
import { motion } from 'framer-motion';
import { AppLayout } from '@/components/layout/AppLayout';
import { AppHeader } from '@/components/layout/AppHeader';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { useToast } from '@/hooks/use-toast';
import { useTariff } from '@/contexts/TariffContext';
import { BillBreakdownChart } from '@/components/tariff/BillBreakdownChart';
import { 
  DISCO_LIST, 
  CONSUMER_CATEGORY_LABELS,
  RESIDENTIAL_SUBCATEGORY_LABELS,
  CONNECTION_TYPE_LABELS,
  RESIDENTIAL_PROTECTED_SLABS,
  RESIDENTIAL_UNPROTECTED_SLABS,
  ELECTRICITY_DUTY_RATE,
  GST_RATE,
  GST_THRESHOLD,
  TV_FEE,
  NET_METERING_EXPORT_RATE,
  ConsumerCategory,
  ResidentialSubcategory,
  ConnectionType,
  DiscoCode,
} from '@/data/pakistanTariffs';
import { 
  Zap, 
  Building2, 
  Factory, 
  Tractor, 
  Home, 
  Info, 
  Calculator,
  Save,
  RotateCcw,
  MapPin,
  Receipt,
  SunMedium,
  Gauge,
} from 'lucide-react';

const TariffSettings = () => {
  const { toast } = useToast();
  const { 
    config, 
    updateConfig, 
    resetConfig,
    calculateMonthlyBill,
  } = useTariff();

  // Test calculation state
  const [testUnits, setTestUnits] = useState(350);
  const [testExport, setTestExport] = useState(100);
  const testBill = calculateMonthlyBill(testUnits, testExport);

  const handleSave = () => {
    toast({
      title: "Tariff Settings Saved",
      description: "Your electricity tariff configuration has been updated.",
    });
  };

  const handleReset = () => {
    resetConfig();
    toast({
      title: "Settings Reset",
      description: "Tariff settings have been reset to defaults.",
    });
  };

  const getCategoryIcon = (category: ConsumerCategory) => {
    switch (category) {
      case 'residential': return <Home className="h-4 w-4" />;
      case 'commercial': return <Building2 className="h-4 w-4" />;
      case 'industrial': return <Factory className="h-4 w-4" />;
      case 'agricultural': return <Tractor className="h-4 w-4" />;
    }
  };

  const formatCurrency = (amount: number) => {
    return `Rs. ${amount.toLocaleString('en-PK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const selectedDisco = DISCO_LIST.find(d => d.code === config.disco);
  const currentSlabs = config.residentialSubcategory === 'protected' 
    ? RESIDENTIAL_PROTECTED_SLABS 
    : RESIDENTIAL_UNPROTECTED_SLABS;

  return (
    <AppLayout>
      <AppHeader 
        title="Tariff Settings" 
        subtitle="Configure Pakistani DISCO electricity tariff"
      />
      
      <div className="p-6 space-y-6 max-w-4xl mx-auto">
        {/* DISCO Selection */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-primary" />
                Distribution Company (DISCO)
              </CardTitle>
              <CardDescription>
                Select your electricity distribution company
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Select DISCO</Label>
                <Select
                  value={config.disco}
                  onValueChange={(value: DiscoCode) => updateConfig({ disco: value })}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select your DISCO" />
                  </SelectTrigger>
                  <SelectContent>
                    {DISCO_LIST.map((disco) => (
                      <SelectItem key={disco.code} value={disco.code}>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{disco.name}</span>
                          <span className="text-muted-foreground text-xs">- {disco.region}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              {selectedDisco && (
                <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/50">
                  <MapPin className="h-5 w-5 text-primary mt-0.5" />
                  <div>
                    <p className="font-medium">{selectedDisco.fullName}</p>
                    <p className="text-sm text-muted-foreground">{selectedDisco.region}</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Consumer Category */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5 text-primary" />
                Consumer Category
              </CardTitle>
              <CardDescription>
                Select your connection type and category
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Category Selection */}
              <div className="space-y-3">
                <Label>Category</Label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {(Object.entries(CONSUMER_CATEGORY_LABELS) as [ConsumerCategory, string][]).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => updateConfig({ 
                        consumerCategory: key,
                        residentialSubcategory: key === 'residential' ? config.residentialSubcategory : undefined,
                      })}
                      className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-all ${
                        config.consumerCategory === key
                          ? 'border-primary bg-primary/5'
                          : 'border-muted hover:border-muted-foreground/30'
                      }`}
                    >
                      {getCategoryIcon(key)}
                      <span className="text-sm font-medium">{label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Residential Subcategory */}
              {config.consumerCategory === 'residential' && (
                <div className="space-y-3">
                  <Label>Subcategory</Label>
                  <div className="grid grid-cols-2 gap-3">
                    {(Object.entries(RESIDENTIAL_SUBCATEGORY_LABELS) as [ResidentialSubcategory, string][]).map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        onClick={() => updateConfig({ residentialSubcategory: key })}
                        className={`p-4 rounded-lg border-2 transition-all text-left ${
                          config.residentialSubcategory === key
                            ? 'border-primary bg-primary/5'
                            : 'border-muted hover:border-muted-foreground/30'
                        }`}
                      >
                        <p className="font-medium">{label}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {key === 'protected' 
                            ? 'Lower rates for consumers using ≤200 units' 
                            : 'Standard rates for all usage levels'}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Connection Type */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Connection Type</Label>
                  <Select
                    value={config.connectionType}
                    onValueChange={(value: ConnectionType) => updateConfig({ connectionType: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.entries(CONNECTION_TYPE_LABELS) as [ConnectionType, string][]).map(([key, label]) => (
                        <SelectItem key={key} value={key}>{label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Sanctioned Load (kW)</Label>
                  <Input
                    type="number"
                    min={1}
                    max={500}
                    value={config.sanctionedLoad}
                    onChange={(e) => updateConfig({ sanctionedLoad: parseFloat(e.target.value) || 1 })}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Net Metering */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <SunMedium className="h-5 w-5 text-primary" />
                Net Metering
              </CardTitle>
              <CardDescription>
                Configure solar export and net metering settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Net Metering Enabled</Label>
                  <p className="text-sm text-muted-foreground">
                    Export excess solar to grid and receive credits
                  </p>
                </div>
                <Switch
                  checked={config.netMeteringEnabled}
                  onCheckedChange={(checked) => updateConfig({ netMeteringEnabled: checked })}
                />
              </div>
              
              {config.netMeteringEnabled && (
                <div className="flex items-center gap-3 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                  <Info className="h-5 w-5 text-green-500" />
                  <div>
                    <p className="text-sm font-medium text-green-600 dark:text-green-400">
                      NEPRA Approved Export Rate
                    </p>
                    <p className="text-lg font-bold text-green-600 dark:text-green-400">
                      Rs. {NET_METERING_EXPORT_RATE}/kWh
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Monthly Adjustments */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Gauge className="h-5 w-5 text-primary" />
                Monthly Adjustments
              </CardTitle>
              <CardDescription>
                Fuel Price Adjustment (FPA) and Quarterly Tariff Adjustment (QTA)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Fuel Price Adjustment (Rs/kWh)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={config.fuelPriceAdjustment}
                    onChange={(e) => updateConfig({ fuelPriceAdjustment: parseFloat(e.target.value) || 0 })}
                  />
                  <p className="text-xs text-muted-foreground">Updated monthly based on fuel costs</p>
                </div>

                <div className="space-y-2">
                  <Label>Quarterly Tariff Adjustment (Rs/kWh)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={config.quarterlyTariffAdjustment}
                    onChange={(e) => updateConfig({ quarterlyTariffAdjustment: parseFloat(e.target.value) || 0 })}
                  />
                  <p className="text-xs text-muted-foreground">Adjusted quarterly by NEPRA</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Tariff Slabs Reference */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <Accordion type="single" collapsible>
            <AccordionItem value="slabs">
              <AccordionTrigger className="text-left">
                <div className="flex items-center gap-2">
                  <Receipt className="h-5 w-5 text-primary" />
                  <span>Current Tariff Slabs</span>
                  <Badge variant="secondary" className="ml-2">
                    {config.consumerCategory === 'residential' 
                      ? config.residentialSubcategory === 'protected' ? 'Protected' : 'Unprotected'
                      : CONSUMER_CATEGORY_LABELS[config.consumerCategory]}
                  </Badge>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-4 pt-4">
                  {config.consumerCategory === 'residential' && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b">
                            <th className="text-left py-2 px-3">Units Range</th>
                            <th className="text-right py-2 px-3">Rate (Rs/kWh)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {currentSlabs.map((slab, index) => (
                            <tr key={index} className="border-b border-muted">
                              <td className="py-2 px-3">
                                {slab.minUnits} - {slab.maxUnits ?? '∞'} units
                              </td>
                              <td className="text-right py-2 px-3 font-mono font-medium">
                                Rs. {slab.ratePerKwh.toFixed(2)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  
                  <Separator />
                  
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div className="space-y-2">
                      <p className="font-medium">Additional Charges:</p>
                      <ul className="space-y-1 text-muted-foreground">
                        <li>• Electricity Duty: {(ELECTRICITY_DUTY_RATE * 100).toFixed(1)}%</li>
                        <li>• GST: {(GST_RATE * 100)}% (on bills &gt; Rs. {GST_THRESHOLD.toLocaleString()})</li>
                        <li>• TV Fee: Rs. {TV_FEE}</li>
                      </ul>
                    </div>
                    <div className="space-y-2">
                      <p className="font-medium">Fixed Charges (Monthly):</p>
                      <ul className="space-y-1 text-muted-foreground">
                        <li>• Single Phase: Rs. 75</li>
                        <li>• Three Phase: Rs. 150</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </motion.div>

        {/* Bill Calculator */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <Card className="border-primary/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calculator className="h-5 w-5 text-primary" />
                Bill Calculator
              </CardTitle>
              <CardDescription>
                Test your tariff configuration with sample values
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Units Consumed</Label>
                  <Input
                    type="number"
                    min={0}
                    value={testUnits}
                    onChange={(e) => setTestUnits(parseInt(e.target.value) || 0)}
                  />
              </div>
              
              {config.netMeteringEnabled && (
                <div className="space-y-2">
                  <Label>Units Exported</Label>
                  <Input
                    type="number"
                    min={0}
                    value={testExport}
                    onChange={(e) => setTestExport(parseInt(e.target.value) || 0)}
                  />
                </div>
              )}
            </div>

            <Separator />

            {/* Visual Bill Breakdown Chart */}
            <BillBreakdownChart bill={testBill} />

            <Separator />

            {/* Detailed Bill Breakdown */}
            <div className="space-y-3">
              <p className="text-sm font-medium text-muted-foreground">Detailed Breakdown</p>
              <div className="flex justify-between text-sm">
                <span>Energy Charges</span>
                <span className="font-mono">{formatCurrency(testBill.energyCharges)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Fixed Charges</span>
                <span className="font-mono">{formatCurrency(testBill.fixedCharges)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Fuel Price Adjustment</span>
                <span className="font-mono">{formatCurrency(testBill.fuelPriceAdjustment)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Quarterly Adjustment</span>
                <span className="font-mono">{formatCurrency(testBill.quarterlyTariffAdjustment)}</span>
              </div>
              <Separator />
              <div className="flex justify-between text-sm">
                <span>Electricity Duty (1.5%)</span>
                <span className="font-mono">{formatCurrency(testBill.electricityDuty)}</span>
              </div>
              {testBill.gst > 0 && (
                <div className="flex justify-between text-sm">
                  <span>GST (17%)</span>
                  <span className="font-mono">{formatCurrency(testBill.gst)}</span>
                </div>
              )}
              <div className="flex justify-between text-sm">
                <span>TV Fee</span>
                <span className="font-mono">{formatCurrency(testBill.tvFee)}</span>
              </div>
              {config.netMeteringEnabled && testBill.exportCredits > 0 && (
                <div className="flex justify-between text-sm text-green-600 dark:text-green-400">
                  <span>Export Credits ({testExport} units)</span>
                  <span className="font-mono">-{formatCurrency(testBill.exportCredits)}</span>
                </div>
              )}
              <Separator />
              <div className="flex justify-between text-lg font-bold">
                <span>Total Amount</span>
                <span className="font-mono text-primary">{formatCurrency(testBill.totalAmount)}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

        {/* Action Buttons */}
        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={handleReset}>
            <RotateCcw className="h-4 w-4 mr-2" />
            Reset to Defaults
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Settings
          </Button>
        </div>
      </div>
    </AppLayout>
  );
};

export default TariffSettings;
