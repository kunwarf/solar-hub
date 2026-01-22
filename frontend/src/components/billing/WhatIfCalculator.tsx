import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  SunMedium, 
  Battery, 
  Receipt, 
  TrendingUp, 
  Calculator,
  ChevronDown,
  ChevronUp,
  Bookmark,
  BookmarkCheck,
  ArrowRight,
  Zap,
  Clock,
  Percent,
  PiggyBank,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import { useTariff } from '@/contexts/TariffContext';
import { cn } from '@/lib/utils';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Legend,
  Cell,
} from 'recharts';
import { 
  DISCO_LIST, 
  CONSUMER_CATEGORY_LABELS,
  ConsumerCategory,
  DiscoCode,
} from '@/data/pakistanTariffs';

interface SavedScenario {
  id: string;
  name: string;
  type: 'panels' | 'battery' | 'tariff' | 'load';
  params: Record<string, any>;
  savings: number;
  createdAt: Date;
}

interface ScenarioResult {
  current: number;
  projected: number;
  difference: number;
  percentChange: number;
}

// Current system baseline (mock data - typical Pakistani residential prosumer)
const CURRENT_SYSTEM = {
  solarCapacity: 8, // kW
  batteryCapacity: 10, // kWh
  monthlyGeneration: 960, // kWh
  monthlyConsumption: 700, // kWh
  monthlyImport: 250, // kWh (grid import when solar insufficient)
  monthlyExport: 510, // kWh (excess solar exported)
  selfConsumption: 64, // %
  backupHours: 3.3,
  currentLoad: 3, // kW average
  importRate: 24.40, // Rs/kWh average slab rate
  exportRate: 19.32, // Rs/kWh net metering rate
};

// Simple bill calculator for scenarios (based on Pakistani tariff structure)
const calculateSimpleBill = (importKwh: number, exportKwh: number) => {
  // Slab-based calculation
  let energyCharges = 0;
  let remaining = importKwh;
  
  // Simplified slab structure
  const slabs = [
    { max: 100, rate: 7.74 },
    { max: 200, rate: 10.06 },
    { max: 300, rate: 14.82 },
    { max: 700, rate: 24.40 },
    { max: Infinity, rate: 30.72 },
  ];
  
  let prevMax = 0;
  for (const slab of slabs) {
    const slabUnits = Math.min(remaining, slab.max - prevMax);
    if (slabUnits > 0) {
      energyCharges += slabUnits * slab.rate;
      remaining -= slabUnits;
    }
    prevMax = slab.max;
    if (remaining <= 0) break;
  }
  
  const fixedCharges = 150; // 3-phase fixed
  const fpaQta = importKwh * 4.68; // FPA + QTA combined
  const subtotal = energyCharges + fixedCharges + fpaQta;
  const electricityDuty = subtotal * 0.015;
  const gst = subtotal > 25000 ? subtotal * 0.17 : 0;
  const tvFee = 35;
  const exportCredit = exportKwh * CURRENT_SYSTEM.exportRate;
  const total = subtotal + electricityDuty + gst + tvFee - exportCredit;
  return Math.max(0, Math.round(total));
};

export function WhatIfCalculator() {
  const { toast } = useToast();
  const { config } = useTariff();
  const [expanded, setExpanded] = useState(true);
  const [savedScenarios, setSavedScenarios] = useState<SavedScenario[]>([]);

  // Scenario states
  const [additionalPanels, setAdditionalPanels] = useState(5);
  const [additionalBattery, setAdditionalBattery] = useState(10);
  const [selectedDisco, setSelectedDisco] = useState<DiscoCode>(config.disco);
  const [selectedCategory, setSelectedCategory] = useState<ConsumerCategory>(config.consumerCategory);
  const [additionalLoad, setAdditionalLoad] = useState(100);

  // Calculate scenarios
  const panelScenario = useMemo(() => {
    const additionalGeneration = additionalPanels * 120; // ~120 kWh/kW/month average
    const newGeneration = CURRENT_SYSTEM.monthlyGeneration + additionalGeneration;
    const additionalExport = Math.max(0, additionalGeneration - (CURRENT_SYSTEM.monthlyImport * 0.8));
    const newExport = CURRENT_SYSTEM.monthlyExport + additionalExport;
    const newImport = Math.max(0, CURRENT_SYSTEM.monthlyImport - additionalGeneration * 0.5);
    
    // Calculate bills
    const currentBill = calculateSimpleBill(CURRENT_SYSTEM.monthlyImport, CURRENT_SYSTEM.monthlyExport);
    const newBill = calculateSimpleBill(newImport, newExport);
    const monthlySavings = currentBill - newBill;
    const annualSavings = monthlySavings * 12;
    
    // ROI calculation (assuming Rs 80,000/kW installed cost)
    const installationCost = additionalPanels * 80000;
    const paybackYears = annualSavings > 0 ? installationCost / annualSavings : Infinity;

    return {
      additionalGeneration,
      newGeneration,
      additionalExport,
      newExport,
      newImport,
      currentBill,
      newBill,
      monthlySavings,
      annualSavings,
      installationCost,
      paybackYears: paybackYears > 0 && isFinite(paybackYears) ? paybackYears : 0,
    };
  }, [additionalPanels]);

  const batteryScenario = useMemo(() => {
    const newCapacity = CURRENT_SYSTEM.batteryCapacity + additionalBattery;
    const additionalBackupHours = (additionalBattery / CURRENT_SYSTEM.currentLoad);
    const newBackupHours = CURRENT_SYSTEM.backupHours + additionalBackupHours;
    
    // More self-consumption = less import, less export
    const selfConsumptionIncrease = Math.min(15, additionalBattery * 0.8); // Max 15% increase
    const newSelfConsumption = Math.min(95, CURRENT_SYSTEM.selfConsumption + selfConsumptionIncrease);
    
    const importReduction = (selfConsumptionIncrease / 100) * CURRENT_SYSTEM.monthlyConsumption;
    const newImport = Math.max(0, CURRENT_SYSTEM.monthlyImport - importReduction);
    const newExport = CURRENT_SYSTEM.monthlyExport - importReduction * 0.5;
    
    const currentBill = calculateSimpleBill(CURRENT_SYSTEM.monthlyImport, CURRENT_SYSTEM.monthlyExport);
    const newBill = calculateSimpleBill(newImport, newExport);
    const monthlySavings = currentBill - newBill;
    
    // Battery cost (assuming Rs 15,000/kWh)
    const batteryCost = additionalBattery * 15000;
    const annualSavings = monthlySavings * 12;
    const paybackYears = annualSavings > 0 ? batteryCost / annualSavings : Infinity;

    return {
      newCapacity,
      additionalBackupHours,
      newBackupHours,
      selfConsumptionIncrease,
      newSelfConsumption,
      currentBill,
      newBill,
      monthlySavings,
      annualSavings,
      batteryCost,
      paybackYears: paybackYears > 0 && isFinite(paybackYears) ? paybackYears : 0,
    };
  }, [additionalBattery]);

  const tariffScenario = useMemo(() => {
    const currentBill = calculateSimpleBill(CURRENT_SYSTEM.monthlyImport, CURRENT_SYSTEM.monthlyExport);
    
    // Simulate with different tariff category - different rate multipliers
    let multiplier = 1;
    if (selectedCategory === 'commercial') multiplier = 1.25;
    if (selectedCategory === 'industrial') multiplier = 0.85;
    if (selectedCategory === 'agricultural') multiplier = 0.75;
    
    const newBillAmount = currentBill * multiplier;
    const difference = newBillAmount - currentBill;

    return {
      currentDisco: config.disco,
      newDisco: selectedDisco,
      currentCategory: config.consumerCategory,
      newCategory: selectedCategory,
      currentBill,
      newBill: newBillAmount,
      difference,
      isSaving: difference < 0,
      monthlySavings: difference < 0 ? Math.abs(difference) : 0,
      annualSavings: (difference < 0 ? Math.abs(difference) : 0) * 12,
    };
  }, [selectedDisco, selectedCategory, config]);

  const loadScenario = useMemo(() => {
    const newConsumption = CURRENT_SYSTEM.monthlyConsumption + additionalLoad;
    const additionalImport = additionalLoad; // Simplified: additional load = additional import
    const newImport = CURRENT_SYSTEM.monthlyImport + additionalImport;
    const newExport = Math.max(0, CURRENT_SYSTEM.monthlyExport - additionalLoad * 0.3);
    
    const newSelfSufficiency = Math.max(0, ((newConsumption - newImport) / newConsumption) * 100);
    
    const currentBill = calculateSimpleBill(CURRENT_SYSTEM.monthlyImport, CURRENT_SYSTEM.monthlyExport);
    const newBill = calculateSimpleBill(newImport, newExport);
    const billIncrease = newBill - currentBill;

    return {
      currentConsumption: CURRENT_SYSTEM.monthlyConsumption,
      newConsumption,
      additionalImport,
      newImport,
      currentSelfSufficiency: CURRENT_SYSTEM.selfConsumption,
      newSelfSufficiency,
      currentBill,
      newBill,
      billIncrease,
      annualIncrease: billIncrease * 12,
    };
  }, [additionalLoad]);

  const handleSaveScenario = (type: 'panels' | 'battery' | 'tariff' | 'load') => {
    let name = '';
    let params: Record<string, any> = {};
    let savings = 0;

    switch (type) {
      case 'panels':
        name = `Add ${additionalPanels}kW Solar`;
        params = { additionalPanels };
        savings = panelScenario.annualSavings;
        break;
      case 'battery':
        name = `Add ${additionalBattery}kWh Battery`;
        params = { additionalBattery };
        savings = batteryScenario.annualSavings;
        break;
      case 'tariff':
        name = `Switch to ${selectedCategory}`;
        params = { selectedDisco, selectedCategory };
        savings = tariffScenario.annualSavings;
        break;
      case 'load':
        name = `Add ${additionalLoad}kWh Load`;
        params = { additionalLoad };
        savings = -loadScenario.annualIncrease;
        break;
    }

    const newScenario: SavedScenario = {
      id: `scenario-${Date.now()}`,
      name,
      type,
      params,
      savings,
      createdAt: new Date(),
    };

    setSavedScenarios(prev => [...prev, newScenario]);
    toast({
      title: 'Scenario Saved',
      description: `"${name}" has been saved to your comparisons.`,
    });
  };

  const formatCurrency = (amount: number) => {
    return `Rs. ${Math.round(amount).toLocaleString()}`;
  };

  const ComparisonChart = ({ current, projected, label }: { current: number; projected: number; label: string }) => {
    const data = [
      { name: 'Current', value: current, fill: 'hsl(var(--muted-foreground))' },
      { name: 'Projected', value: projected, fill: projected < current ? 'hsl(var(--success))' : 'hsl(var(--destructive))' },
    ];

    return (
      <div className="h-[120px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 30, left: 0, bottom: 0 }}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" width={70} tick={{ fontSize: 12 }} />
            <Tooltip
              formatter={(value: number) => [formatCurrency(value), label]}
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
              }}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  };

  const ComparisonTable = ({ rows }: { rows: { label: string; current: string | number; projected: string | number; highlight?: boolean }[] }) => (
    <div className="space-y-2">
      {rows.map((row, idx) => (
        <div 
          key={idx} 
          className={cn(
            "grid grid-cols-3 gap-4 py-2 px-3 rounded-lg text-sm",
            row.highlight ? "bg-success/10 font-semibold" : "bg-muted/30"
          )}
        >
          <span className="text-muted-foreground">{row.label}</span>
          <span className="text-center font-mono">{row.current}</span>
          <span className={cn(
            "text-center font-mono",
            row.highlight && "text-success"
          )}>{row.projected}</span>
        </div>
      ))}
    </div>
  );

  return (
    <Card className="border-primary/20">
      <CardHeader 
        className="cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Calculator className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">What-If Scenario Calculator</CardTitle>
              <CardDescription>Explore different system configurations and their impact</CardDescription>
            </div>
          </div>
          <Button variant="ghost" size="icon">
            {expanded ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
          </Button>
        </div>
      </CardHeader>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <CardContent className="space-y-6">
              {/* Saved Scenarios */}
              {savedScenarios.length > 0 && (
                <div className="p-4 rounded-lg bg-muted/50 border">
                  <div className="flex items-center gap-2 mb-3">
                    <BookmarkCheck className="h-4 w-4 text-primary" />
                    <span className="font-medium text-sm">Saved Scenarios</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {savedScenarios.map(scenario => (
                      <Badge key={scenario.id} variant="secondary" className="gap-1">
                        {scenario.name}
                        <span className={cn(
                          "ml-1 font-mono text-xs",
                          scenario.savings >= 0 ? "text-success" : "text-destructive"
                        )}>
                          {scenario.savings >= 0 ? '+' : ''}{formatCurrency(scenario.savings)}/yr
                        </span>
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              <Tabs defaultValue="panels" className="space-y-4">
                <TabsList className="grid grid-cols-4 w-full">
                  <TabsTrigger value="panels" className="gap-1.5 text-xs sm:text-sm">
                    <SunMedium className="h-4 w-4" />
                    <span className="hidden sm:inline">Add Panels</span>
                  </TabsTrigger>
                  <TabsTrigger value="battery" className="gap-1.5 text-xs sm:text-sm">
                    <Battery className="h-4 w-4" />
                    <span className="hidden sm:inline">Add Battery</span>
                  </TabsTrigger>
                  <TabsTrigger value="tariff" className="gap-1.5 text-xs sm:text-sm">
                    <Receipt className="h-4 w-4" />
                    <span className="hidden sm:inline">Change Tariff</span>
                  </TabsTrigger>
                  <TabsTrigger value="load" className="gap-1.5 text-xs sm:text-sm">
                    <TrendingUp className="h-4 w-4" />
                    <span className="hidden sm:inline">Increase Load</span>
                  </TabsTrigger>
                </TabsList>

                {/* Add Panels Scenario */}
                <TabsContent value="panels" className="space-y-4">
                  <div className="grid gap-6 lg:grid-cols-2">
                    <div className="space-y-4">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <Label>Additional Solar Capacity</Label>
                          <Badge variant="outline" className="font-mono">{additionalPanels} kW</Badge>
                        </div>
                        <Slider
                          value={[additionalPanels]}
                          onValueChange={([val]) => setAdditionalPanels(val)}
                          min={1}
                          max={20}
                          step={1}
                          className="w-full"
                        />
                        <div className="flex justify-between text-xs text-muted-foreground">
                          <span>1 kW</span>
                          <span>20 kW</span>
                        </div>
                      </div>

                      <Separator />

                      <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 rounded-lg bg-solar/10 border border-solar/20">
                          <div className="flex items-center gap-2 text-solar mb-1">
                            <Zap className="h-4 w-4" />
                            <span className="text-xs">Extra Generation</span>
                          </div>
                          <p className="text-lg font-bold text-foreground">
                            +{panelScenario.additionalGeneration} kWh/mo
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-success/10 border border-success/20">
                          <div className="flex items-center gap-2 text-success mb-1">
                            <PiggyBank className="h-4 w-4" />
                            <span className="text-xs">Monthly Savings</span>
                          </div>
                          <p className="text-lg font-bold text-foreground">
                            {formatCurrency(panelScenario.monthlySavings)}
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-info/10 border border-info/20">
                          <div className="flex items-center gap-2 text-info mb-1">
                            <Clock className="h-4 w-4" />
                            <span className="text-xs">Payback Period</span>
                          </div>
                          <p className="text-lg font-bold text-foreground">
                            {panelScenario.paybackYears.toFixed(1)} years
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
                          <div className="flex items-center gap-2 text-primary mb-1">
                            <Receipt className="h-4 w-4" />
                            <span className="text-xs">Installation Cost</span>
                          </div>
                          <p className="text-lg font-bold text-foreground">
                            {formatCurrency(panelScenario.installationCost)}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="grid grid-cols-3 gap-2 text-center text-xs font-medium">
                        <span></span>
                        <span className="text-muted-foreground">Current</span>
                        <span className="text-primary">Projected</span>
                      </div>
                      <ComparisonTable rows={[
                        { label: 'Monthly Generation', current: `${CURRENT_SYSTEM.monthlyGeneration} kWh`, projected: `${panelScenario.newGeneration} kWh` },
                        { label: 'Grid Export', current: `${CURRENT_SYSTEM.monthlyExport} kWh`, projected: `${Math.round(panelScenario.newExport)} kWh` },
                        { label: 'Grid Import', current: `${CURRENT_SYSTEM.monthlyImport} kWh`, projected: `${Math.round(panelScenario.newImport)} kWh` },
                        { label: 'Monthly Bill', current: formatCurrency(panelScenario.currentBill), projected: formatCurrency(panelScenario.newBill), highlight: true },
                      ]} />

                      <ComparisonChart 
                        current={panelScenario.currentBill} 
                        projected={panelScenario.newBill} 
                        label="Monthly Bill"
                      />

                      <div className="p-4 rounded-lg bg-success/10 border border-success/20 text-center">
                        <p className="text-sm text-muted-foreground">Annual Savings</p>
                        <p className="text-2xl font-bold text-success">
                          {formatCurrency(panelScenario.annualSavings)}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <Button onClick={() => handleSaveScenario('panels')} variant="outline" className="gap-2">
                      <Bookmark className="h-4 w-4" />
                      Save Scenario
                    </Button>
                  </div>
                </TabsContent>

                {/* Add Battery Scenario */}
                <TabsContent value="battery" className="space-y-4">
                  <div className="grid gap-6 lg:grid-cols-2">
                    <div className="space-y-4">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <Label>Additional Battery Capacity</Label>
                          <Badge variant="outline" className="font-mono">{additionalBattery} kWh</Badge>
                        </div>
                        <Slider
                          value={[additionalBattery]}
                          onValueChange={([val]) => setAdditionalBattery(val)}
                          min={5}
                          max={50}
                          step={5}
                          className="w-full"
                        />
                        <div className="flex justify-between text-xs text-muted-foreground">
                          <span>5 kWh</span>
                          <span>50 kWh</span>
                        </div>
                      </div>

                      <Separator />

                      <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 rounded-lg bg-battery/10 border border-battery/20">
                          <div className="flex items-center gap-2 text-battery mb-1">
                            <Clock className="h-4 w-4" />
                            <span className="text-xs">Extra Backup</span>
                          </div>
                          <p className="text-lg font-bold text-foreground">
                            +{batteryScenario.additionalBackupHours.toFixed(1)} hrs
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-success/10 border border-success/20">
                          <div className="flex items-center gap-2 text-success mb-1">
                            <Percent className="h-4 w-4" />
                            <span className="text-xs">Self-Consumption</span>
                          </div>
                          <p className="text-lg font-bold text-foreground">
                            +{batteryScenario.selfConsumptionIncrease.toFixed(0)}%
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-info/10 border border-info/20">
                          <div className="flex items-center gap-2 text-info mb-1">
                            <Clock className="h-4 w-4" />
                            <span className="text-xs">Payback Period</span>
                          </div>
                          <p className="text-lg font-bold text-foreground">
                            {batteryScenario.paybackYears > 0 ? `${batteryScenario.paybackYears.toFixed(1)} years` : 'N/A'}
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
                          <div className="flex items-center gap-2 text-primary mb-1">
                            <Receipt className="h-4 w-4" />
                            <span className="text-xs">Battery Cost</span>
                          </div>
                          <p className="text-lg font-bold text-foreground">
                            {formatCurrency(batteryScenario.batteryCost)}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="grid grid-cols-3 gap-2 text-center text-xs font-medium">
                        <span></span>
                        <span className="text-muted-foreground">Current</span>
                        <span className="text-primary">Projected</span>
                      </div>
                      <ComparisonTable rows={[
                        { label: 'Battery Capacity', current: `${CURRENT_SYSTEM.batteryCapacity} kWh`, projected: `${batteryScenario.newCapacity} kWh` },
                        { label: 'Backup Hours', current: `${CURRENT_SYSTEM.backupHours} hrs`, projected: `${batteryScenario.newBackupHours.toFixed(1)} hrs` },
                        { label: 'Self-Consumption', current: `${CURRENT_SYSTEM.selfConsumption}%`, projected: `${batteryScenario.newSelfConsumption.toFixed(0)}%` },
                        { label: 'Monthly Bill', current: formatCurrency(batteryScenario.currentBill), projected: formatCurrency(batteryScenario.newBill), highlight: true },
                      ]} />

                      <ComparisonChart 
                        current={batteryScenario.currentBill} 
                        projected={batteryScenario.newBill} 
                        label="Monthly Bill"
                      />

                      <div className="p-4 rounded-lg bg-success/10 border border-success/20 text-center">
                        <p className="text-sm text-muted-foreground">Annual Savings</p>
                        <p className="text-2xl font-bold text-success">
                          {formatCurrency(batteryScenario.annualSavings)}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <Button onClick={() => handleSaveScenario('battery')} variant="outline" className="gap-2">
                      <Bookmark className="h-4 w-4" />
                      Save Scenario
                    </Button>
                  </div>
                </TabsContent>

                {/* Change Tariff Scenario */}
                <TabsContent value="tariff" className="space-y-4">
                  <div className="grid gap-6 lg:grid-cols-2">
                    <div className="space-y-4">
                      <div className="space-y-3">
                        <Label>Select DISCO</Label>
                        <Select value={selectedDisco} onValueChange={(val: DiscoCode) => setSelectedDisco(val)}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {DISCO_LIST.map(disco => (
                              <SelectItem key={disco.code} value={disco.code}>
                                {disco.name} - {disco.region}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-3">
                        <Label>Consumer Category</Label>
                        <Select value={selectedCategory} onValueChange={(val: ConsumerCategory) => setSelectedCategory(val)}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {(Object.entries(CONSUMER_CATEGORY_LABELS) as [ConsumerCategory, string][]).map(([key, label]) => (
                              <SelectItem key={key} value={key}>{label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      <Separator />

                      <div className="p-4 rounded-lg border bg-muted/30">
                        <div className="flex items-center justify-between mb-4">
                          <span className="text-sm text-muted-foreground">Current Plan</span>
                          <ArrowRight className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm text-muted-foreground">New Plan</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium">{config.disco}</p>
                            <p className="text-sm text-muted-foreground capitalize">{config.consumerCategory}</p>
                          </div>
                          <ArrowRight className="h-5 w-5 text-primary" />
                          <div className="text-right">
                            <p className="font-medium">{selectedDisco}</p>
                            <p className="text-sm text-muted-foreground capitalize">{selectedCategory}</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="grid grid-cols-3 gap-2 text-center text-xs font-medium">
                        <span></span>
                        <span className="text-muted-foreground">Current</span>
                        <span className="text-primary">New Plan</span>
                      </div>
                      <ComparisonTable rows={[
                        { label: 'DISCO', current: config.disco, projected: selectedDisco },
                        { label: 'Category', current: CONSUMER_CATEGORY_LABELS[config.consumerCategory], projected: CONSUMER_CATEGORY_LABELS[selectedCategory] },
                        { label: 'Monthly Bill', current: formatCurrency(tariffScenario.currentBill), projected: formatCurrency(tariffScenario.newBill), highlight: true },
                      ]} />

                      <ComparisonChart 
                        current={tariffScenario.currentBill} 
                        projected={tariffScenario.newBill} 
                        label="Monthly Bill"
                      />

                      <div className={cn(
                        "p-4 rounded-lg border text-center",
                        tariffScenario.isSaving 
                          ? "bg-success/10 border-success/20" 
                          : "bg-destructive/10 border-destructive/20"
                      )}>
                        <p className="text-sm text-muted-foreground">
                          {tariffScenario.isSaving ? 'Annual Savings' : 'Additional Annual Cost'}
                        </p>
                        <p className={cn(
                          "text-2xl font-bold",
                          tariffScenario.isSaving ? "text-success" : "text-destructive"
                        )}>
                          {tariffScenario.isSaving ? '+' : ''}{formatCurrency(Math.abs(tariffScenario.difference * 12))}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <Button onClick={() => handleSaveScenario('tariff')} variant="outline" className="gap-2">
                      <Bookmark className="h-4 w-4" />
                      Save Scenario
                    </Button>
                  </div>
                </TabsContent>

                {/* Increase Load Scenario */}
                <TabsContent value="load" className="space-y-4">
                  <div className="grid gap-6 lg:grid-cols-2">
                    <div className="space-y-4">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <Label>Additional Monthly Consumption</Label>
                          <Badge variant="outline" className="font-mono">{additionalLoad} kWh</Badge>
                        </div>
                        <Slider
                          value={[additionalLoad]}
                          onValueChange={([val]) => setAdditionalLoad(val)}
                          min={0}
                          max={500}
                          step={25}
                          className="w-full"
                        />
                        <div className="flex justify-between text-xs text-muted-foreground">
                          <span>0 kWh</span>
                          <span>500 kWh</span>
                        </div>
                      </div>

                      <Separator />

                      <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 rounded-lg bg-consumption/10 border border-consumption/20">
                          <div className="flex items-center gap-2 text-consumption mb-1">
                            <Zap className="h-4 w-4" />
                            <span className="text-xs">New Consumption</span>
                          </div>
                          <p className="text-lg font-bold text-foreground">
                            {loadScenario.newConsumption} kWh/mo
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-grid/10 border border-grid/20">
                          <div className="flex items-center gap-2 text-grid mb-1">
                            <TrendingUp className="h-4 w-4" />
                            <span className="text-xs">Grid Import</span>
                          </div>
                          <p className="text-lg font-bold text-foreground">
                            +{loadScenario.additionalImport} kWh
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-warning/10 border border-warning/20 col-span-2">
                          <div className="flex items-center gap-2 text-warning mb-1">
                            <Percent className="h-4 w-4" />
                            <span className="text-xs">Self-Sufficiency Change</span>
                          </div>
                          <p className="text-lg font-bold text-foreground">
                            {loadScenario.currentSelfSufficiency}% → {loadScenario.newSelfSufficiency.toFixed(0)}%
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="grid grid-cols-3 gap-2 text-center text-xs font-medium">
                        <span></span>
                        <span className="text-muted-foreground">Current</span>
                        <span className="text-primary">Projected</span>
                      </div>
                      <ComparisonTable rows={[
                        { label: 'Consumption', current: `${loadScenario.currentConsumption} kWh`, projected: `${loadScenario.newConsumption} kWh` },
                        { label: 'Grid Import', current: `${CURRENT_SYSTEM.monthlyImport} kWh`, projected: `${loadScenario.newImport} kWh` },
                        { label: 'Self-Sufficiency', current: `${loadScenario.currentSelfSufficiency}%`, projected: `${loadScenario.newSelfSufficiency.toFixed(0)}%` },
                        { label: 'Monthly Bill', current: formatCurrency(loadScenario.currentBill), projected: formatCurrency(loadScenario.newBill), highlight: true },
                      ]} />

                      <ComparisonChart 
                        current={loadScenario.currentBill} 
                        projected={loadScenario.newBill} 
                        label="Monthly Bill"
                      />

                      <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-center">
                        <p className="text-sm text-muted-foreground">Annual Cost Increase</p>
                        <p className="text-2xl font-bold text-destructive">
                          +{formatCurrency(loadScenario.annualIncrease)}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <Button onClick={() => handleSaveScenario('load')} variant="outline" className="gap-2">
                      <Bookmark className="h-4 w-4" />
                      Save Scenario
                    </Button>
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}
