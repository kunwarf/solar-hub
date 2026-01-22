import { useState } from "react";
import { motion } from "framer-motion";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Brain,
  CloudSun,
  Settings2,
  TrendingUp,
  Battery,
  Zap,
  Clock,
  Sun,
  Moon,
  ChevronRight,
  Activity,
  DollarSign,
  Calendar,
  BarChart3,
  Save,
  RotateCcw,
} from "lucide-react";
import { toast } from "@/hooks/use-toast";

interface ForecastSettings {
  enabled: boolean;
  weatherProvider: string;
  batteryCapacity: number;
  weatherApiKey: string;
  openWeatherKey: string;
}

interface PolicySettings {
  smartSchedulerEnabled: boolean;
  targetFullBeforeSunset: boolean;
  overnightMinSoc: number;
  blackoutReserveSoc: number;
  maxChargePower: number;
  maxDischargePower: number;
  primaryMode: string;
}

interface ScheduleDecision {
  time: string;
  action: "charge" | "discharge" | "hold";
  reason: string;
  power: number;
}

const SmartSchedulerPage = () => {
  const [forecastSettings, setForecastSettings] = useState<ForecastSettings>({
    enabled: true,
    weatherProvider: "openweather",
    batteryCapacity: 20,
    weatherApiKey: "",
    openWeatherKey: "",
  });

  const [policySettings, setPolicySettings] = useState<PolicySettings>({
    smartSchedulerEnabled: true,
    targetFullBeforeSunset: true,
    overnightMinSoc: 35,
    blackoutReserveSoc: 30,
    maxChargePower: 3000,
    maxDischargePower: 5000,
    primaryMode: "self-use",
  });

  // Mock stats data
  const todayStats = {
    predictedSolar: 42.5,
    actualSolar: 38.2,
    savings: 12.45,
    optimizationScore: 94,
    peakShavingSaved: 8.30,
    gridImportAvoided: 15.6,
  };

  const currentSchedule: ScheduleDecision[] = [
    { time: "06:00", action: "hold", reason: "Low solar, maintaining reserve", power: 0 },
    { time: "08:00", action: "charge", reason: "Solar surplus, charging battery", power: 2500 },
    { time: "12:00", action: "charge", reason: "Peak solar production", power: 4000 },
    { time: "16:00", action: "hold", reason: "Pre-sunset buffer", power: 0 },
    { time: "18:00", action: "discharge", reason: "Peak tariff hours", power: 3500 },
    { time: "22:00", action: "hold", reason: "Night mode, reserve maintained", power: 0 },
  ];

  const aiDecisionLog = [
    { timestamp: "Today 14:32", decision: "Increased charge rate", reason: "Cloud clearing detected, maximizing solar capture" },
    { timestamp: "Today 11:15", decision: "Reduced discharge", reason: "Weather forecast updated: cloudy afternoon expected" },
    { timestamp: "Today 06:00", decision: "Morning hold", reason: "Battery at 85% SOC, waiting for solar generation" },
    { timestamp: "Yesterday 18:45", decision: "Peak discharge", reason: "High grid tariff detected, discharging to offset consumption" },
  ];

  const weatherForecast = [
    { day: "Today", condition: "Sunny", solarPotential: 95 },
    { day: "Tomorrow", condition: "Partly Cloudy", solarPotential: 72 },
    { day: "Wed", condition: "Cloudy", solarPotential: 45 },
    { day: "Thu", condition: "Sunny", solarPotential: 88 },
    { day: "Fri", condition: "Rain", solarPotential: 25 },
  ];

  const handleSave = () => {
    toast({
      title: "Settings Saved",
      description: "Smart scheduler configuration has been updated.",
    });
  };

  const handleReset = () => {
    setForecastSettings({
      enabled: true,
      weatherProvider: "openweather",
      batteryCapacity: 20,
      weatherApiKey: "",
      openWeatherKey: "",
    });
    setPolicySettings({
      smartSchedulerEnabled: true,
      targetFullBeforeSunset: true,
      overnightMinSoc: 35,
      blackoutReserveSoc: 30,
      maxChargePower: 3000,
      maxDischargePower: 5000,
      primaryMode: "self-use",
    });
    toast({
      title: "Settings Reset",
      description: "Smart scheduler settings have been restored to defaults.",
    });
  };

  return (
    <AppLayout>
      <AppHeader
        title="Smart Scheduler"
        subtitle="AI-powered battery charging and discharging optimization"
      />

      <div className="p-6 space-y-6">
        <Tabs defaultValue="dashboard" className="space-y-6">
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <TabsList className="glass-card p-1 flex-wrap h-auto">
              <TabsTrigger value="dashboard" className="gap-2">
                <BarChart3 className="w-4 h-4" />
                <span className="hidden sm:inline">Dashboard</span>
              </TabsTrigger>
              <TabsTrigger value="schedule" className="gap-2">
                <Calendar className="w-4 h-4" />
                <span className="hidden sm:inline">Schedule</span>
              </TabsTrigger>
              <TabsTrigger value="settings" className="gap-2">
                <Settings2 className="w-4 h-4" />
                <span className="hidden sm:inline">Settings</span>
              </TabsTrigger>
            </TabsList>
          </motion.div>

          {/* Dashboard Tab */}
          <TabsContent value="dashboard" className="space-y-6">
            {/* Status Banner */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-4"
            >
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-green-500/10">
                  <Brain className="w-6 h-6 text-green-500" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground">Smart Scheduler Active</span>
                    <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/20">
                      Optimizing
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Currently charging at 2.5kW • Next action: Discharge at 6:00 PM
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-primary">{todayStats.optimizationScore}%</div>
                  <div className="text-xs text-muted-foreground">Optimization Score</div>
                </div>
              </div>
            </motion.div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
              >
                <Card className="glass-card border-0">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                      <Sun className="w-4 h-4 text-yellow-500" />
                      Predicted Solar
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-foreground">{todayStats.predictedSolar} kWh</div>
                    <p className="text-xs text-muted-foreground">vs {todayStats.actualSolar} kWh actual</p>
                  </CardContent>
                </Card>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 }}
              >
                <Card className="glass-card border-0">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                      <DollarSign className="w-4 h-4 text-green-500" />
                      Today's Savings
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-green-500">${todayStats.savings}</div>
                    <p className="text-xs text-muted-foreground">From smart scheduling</p>
                  </CardContent>
                </Card>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                <Card className="glass-card border-0">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-primary" />
                      Peak Shaving
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-foreground">${todayStats.peakShavingSaved}</div>
                    <p className="text-xs text-muted-foreground">Tariff avoided</p>
                  </CardContent>
                </Card>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25 }}
              >
                <Card className="glass-card border-0">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                      <Zap className="w-4 h-4 text-orange-500" />
                      Grid Import Avoided
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-foreground">{todayStats.gridImportAvoided} kWh</div>
                    <p className="text-xs text-muted-foreground">Self-consumption</p>
                  </CardContent>
                </Card>
              </motion.div>
            </div>

            {/* Weather Forecast */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="glass-card p-6"
            >
              <div className="flex items-center gap-2 mb-4">
                <CloudSun className="w-5 h-5 text-primary" />
                <h3 className="font-medium text-foreground">Weather Forecast & Solar Potential</h3>
              </div>
              <div className="grid grid-cols-5 gap-4">
                {weatherForecast.map((day, index) => (
                  <div key={index} className="text-center p-3 rounded-lg bg-secondary/30">
                    <div className="text-sm font-medium text-foreground mb-1">{day.day}</div>
                    <div className="text-xs text-muted-foreground mb-2">{day.condition}</div>
                    <div className="relative w-full h-2 bg-secondary rounded-full overflow-hidden">
                      <div
                        className="absolute left-0 top-0 h-full bg-yellow-500 rounded-full"
                        style={{ width: `${day.solarPotential}%` }}
                      />
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">{day.solarPotential}%</div>
                  </div>
                ))}
              </div>
            </motion.div>

            {/* AI Decision Log */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.35 }}
              className="glass-card p-6"
            >
              <div className="flex items-center gap-2 mb-4">
                <Brain className="w-5 h-5 text-primary" />
                <h3 className="font-medium text-foreground">AI Decision Log</h3>
              </div>
              <div className="space-y-3">
                {aiDecisionLog.map((log, index) => (
                  <div key={index} className="flex items-start gap-3 p-3 rounded-lg bg-secondary/30">
                    <div className="w-2 h-2 rounded-full bg-primary mt-2 flex-shrink-0" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-foreground">{log.decision}</span>
                        <span className="text-xs text-muted-foreground">{log.timestamp}</span>
                      </div>
                      <p className="text-sm text-muted-foreground">{log.reason}</p>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          </TabsContent>

          {/* Schedule Tab */}
          <TabsContent value="schedule" className="space-y-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-6"
            >
              <div className="flex items-center gap-2 mb-6">
                <Clock className="w-5 h-5 text-primary" />
                <h3 className="font-medium text-foreground">Today's Schedule</h3>
              </div>

              {/* Timeline Visualization */}
              <div className="relative">
                <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-border" />
                <div className="space-y-4">
                  {currentSchedule.map((item, index) => (
                    <motion.div
                      key={index}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.1 }}
                      className="flex items-start gap-4 pl-8 relative"
                    >
                      <div
                        className={`absolute left-2.5 w-3 h-3 rounded-full border-2 border-background ${
                          item.action === "charge"
                            ? "bg-green-500"
                            : item.action === "discharge"
                            ? "bg-orange-500"
                            : "bg-muted-foreground"
                        }`}
                      />
                      <div className="flex-1 p-4 rounded-lg bg-secondary/30">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-sm text-muted-foreground">{item.time}</span>
                            <Badge
                              variant="outline"
                              className={
                                item.action === "charge"
                                  ? "bg-green-500/10 text-green-500 border-green-500/20"
                                  : item.action === "discharge"
                                  ? "bg-orange-500/10 text-orange-500 border-orange-500/20"
                                  : "bg-muted text-muted-foreground"
                              }
                            >
                              {item.action === "charge" && <Battery className="w-3 h-3 mr-1" />}
                              {item.action === "discharge" && <Zap className="w-3 h-3 mr-1" />}
                              {item.action === "hold" && <Activity className="w-3 h-3 mr-1" />}
                              {item.action.charAt(0).toUpperCase() + item.action.slice(1)}
                            </Badge>
                          </div>
                          {item.power > 0 && (
                            <span className="text-sm font-medium text-foreground">{item.power}W</span>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">{item.reason}</p>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            </motion.div>

            {/* Schedule Summary */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card className="glass-card border-0">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                    <Sun className="w-4 h-4 text-yellow-500" />
                    Morning (6AM-12PM)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-lg font-bold text-green-500">Charging</div>
                  <p className="text-xs text-muted-foreground">Est. 15.2 kWh captured</p>
                </CardContent>
              </Card>

              <Card className="glass-card border-0">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                    <Activity className="w-4 h-4 text-primary" />
                    Afternoon (12PM-6PM)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-lg font-bold text-foreground">Holding</div>
                  <p className="text-xs text-muted-foreground">Battery at target SOC</p>
                </CardContent>
              </Card>

              <Card className="glass-card border-0">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                    <Moon className="w-4 h-4 text-blue-500" />
                    Evening (6PM-10PM)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-lg font-bold text-orange-500">Discharging</div>
                  <p className="text-xs text-muted-foreground">Peak tariff optimization</p>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Settings Tab */}
          <TabsContent value="settings" className="space-y-4">
            <Accordion type="multiple" defaultValue={["forecast", "policy"]} className="space-y-4">
              {/* Forecast Settings */}
              <AccordionItem value="forecast" className="glass-card border-0">
                <AccordionTrigger className="px-6 py-4 hover:no-underline">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <CloudSun className="w-5 h-5 text-primary" />
                    </div>
                    <div className="text-left">
                      <p className="font-medium text-foreground">Forecast Settings</p>
                      <p className="text-sm text-muted-foreground">Weather forecast and solar generation prediction</p>
                    </div>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-6 pb-6">
                  <div className="space-y-6 pt-4">
                    <div className="flex items-center justify-between p-4 rounded-lg bg-secondary/30">
                      <div>
                        <p className="font-medium text-foreground">Forecast Enabled</p>
                        <p className="text-sm text-muted-foreground">Enable solar forecasting</p>
                      </div>
                      <Switch
                        checked={forecastSettings.enabled}
                        onCheckedChange={(checked) =>
                          setForecastSettings({ ...forecastSettings, enabled: checked })
                        }
                      />
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <Label>Weather Provider</Label>
                        <p className="text-xs text-muted-foreground">Weather forecast provider</p>
                        <Select
                          value={forecastSettings.weatherProvider}
                          onValueChange={(value) =>
                            setForecastSettings({ ...forecastSettings, weatherProvider: value })
                          }
                        >
                          <SelectTrigger className="bg-secondary/50">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="openweather">OpenWeather</SelectItem>
                            <SelectItem value="weatherapi">WeatherAPI</SelectItem>
                            <SelectItem value="visualcrossing">Visual Crossing</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-2">
                        <Label>Battery Capacity (kWh)</Label>
                        <p className="text-xs text-muted-foreground">Total battery capacity in kWh</p>
                        <Input
                          type="number"
                          value={forecastSettings.batteryCapacity}
                          onChange={(e) =>
                            setForecastSettings({ ...forecastSettings, batteryCapacity: Number(e.target.value) })
                          }
                          className="bg-secondary/50"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>WeatherAPI Key</Label>
                        <p className="text-xs text-muted-foreground">API key for WeatherAPI.com</p>
                        <Input
                          type="password"
                          value={forecastSettings.weatherApiKey}
                          onChange={(e) =>
                            setForecastSettings({ ...forecastSettings, weatherApiKey: e.target.value })
                          }
                          placeholder="Enter API key..."
                          className="bg-secondary/50"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>OpenWeather Key</Label>
                        <p className="text-xs text-muted-foreground">API key for OpenWeatherMap</p>
                        <Input
                          type="password"
                          value={forecastSettings.openWeatherKey}
                          onChange={(e) =>
                            setForecastSettings({ ...forecastSettings, openWeatherKey: e.target.value })
                          }
                          placeholder="Enter API key..."
                          className="bg-secondary/50"
                        />
                      </div>
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>

              {/* Policy Settings */}
              <AccordionItem value="policy" className="glass-card border-0">
                <AccordionTrigger className="px-6 py-4 hover:no-underline">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <Settings2 className="w-5 h-5 text-primary" />
                    </div>
                    <div className="text-left">
                      <p className="font-medium text-foreground">Policy Settings</p>
                      <p className="text-sm text-muted-foreground">Smart scheduler behavior and battery management policies</p>
                    </div>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-6 pb-6">
                  <div className="space-y-6 pt-4">
                    <div className="flex items-center justify-between p-4 rounded-lg bg-secondary/30">
                      <div>
                        <p className="font-medium text-foreground">Smart Scheduler Enabled</p>
                        <p className="text-sm text-muted-foreground">Enable or disable the smart scheduler</p>
                      </div>
                      <Switch
                        checked={policySettings.smartSchedulerEnabled}
                        onCheckedChange={(checked) =>
                          setPolicySettings({ ...policySettings, smartSchedulerEnabled: checked })
                        }
                      />
                    </div>

                    <div className="flex items-center justify-between p-4 rounded-lg bg-secondary/30">
                      <div>
                        <p className="font-medium text-foreground">Target Full Before Sunset</p>
                        <p className="text-sm text-muted-foreground">Try to reach full charge before sunset</p>
                      </div>
                      <Switch
                        checked={policySettings.targetFullBeforeSunset}
                        onCheckedChange={(checked) =>
                          setPolicySettings({ ...policySettings, targetFullBeforeSunset: checked })
                        }
                      />
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <Label>Overnight Minimum SOC (%)</Label>
                        <p className="text-xs text-muted-foreground">Minimum battery SOC to maintain overnight</p>
                        <Input
                          type="number"
                          value={policySettings.overnightMinSoc}
                          onChange={(e) =>
                            setPolicySettings({ ...policySettings, overnightMinSoc: Number(e.target.value) })
                          }
                          className="bg-secondary/50"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>Blackout Reserve SOC (%)</Label>
                        <p className="text-xs text-muted-foreground">SOC reserve for blackout situations</p>
                        <Input
                          type="number"
                          value={policySettings.blackoutReserveSoc}
                          onChange={(e) =>
                            setPolicySettings({ ...policySettings, blackoutReserveSoc: Number(e.target.value) })
                          }
                          className="bg-secondary/50"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>Maximum Charge Power (W)</Label>
                        <p className="text-xs text-muted-foreground">Maximum battery charging power</p>
                        <Input
                          type="number"
                          value={policySettings.maxChargePower}
                          onChange={(e) =>
                            setPolicySettings({ ...policySettings, maxChargePower: Number(e.target.value) })
                          }
                          className="bg-secondary/50"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>Maximum Discharge Power (W)</Label>
                        <p className="text-xs text-muted-foreground">Maximum battery discharging power</p>
                        <Input
                          type="number"
                          value={policySettings.maxDischargePower}
                          onChange={(e) =>
                            setPolicySettings({ ...policySettings, maxDischargePower: Number(e.target.value) })
                          }
                          className="bg-secondary/50"
                        />
                      </div>

                      <div className="space-y-2 md:col-span-2">
                        <Label>Primary Mode</Label>
                        <p className="text-xs text-muted-foreground">Primary operating mode</p>
                        <Select
                          value={policySettings.primaryMode}
                          onValueChange={(value) =>
                            setPolicySettings({ ...policySettings, primaryMode: value })
                          }
                        >
                          <SelectTrigger className="bg-secondary/50">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="self-use">Self Use</SelectItem>
                            <SelectItem value="time-of-use">Time of Use</SelectItem>
                            <SelectItem value="peak-shaving">Peak Shaving</SelectItem>
                            <SelectItem value="backup">Backup Priority</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>

            {/* Action Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="flex flex-wrap gap-4"
            >
              <Button onClick={handleSave} className="gap-2">
                <Save className="w-4 h-4" />
                Save Changes
              </Button>
              <Button variant="outline" onClick={handleReset} className="gap-2">
                <RotateCcw className="w-4 h-4" />
                Reset to Defaults
              </Button>
            </motion.div>
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
};

export default SmartSchedulerPage;
