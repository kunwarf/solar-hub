import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { format, parseISO } from 'date-fns';
import {
  Zap,
  ZapOff,
  Download,
  Battery,
  Clock,
  AlertTriangle,
  Calendar,
  BarChart3,
  Bell,
  FileSpreadsheet,
  Loader2
} from 'lucide-react';
import { AppLayout } from '@/components/layout/AppLayout';
import { AppHeader } from '@/components/layout/AppHeader';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

import { OutageTimeline } from '@/components/outages/OutageTimeline';
import { OutageCalendar } from '@/components/outages/OutageCalendar';
import { OutageHistoryTable } from '@/components/outages/OutageHistoryTable';
import { OutageStatsCards } from '@/components/outages/OutageStatsCards';
import { OutageAlertsPanel } from '@/components/outages/OutageAlertsPanel';

import dashboardService from '@/api/services/dashboard.service';
import type {
  OutagesData,
  OutageRecord as ApiOutageRecord,
  OutageAlert as ApiOutageAlert,
  DailyOutageSummary as ApiDailySummary,
} from '@/api/services/dashboard.service';
import { formatDuration, exportToCSV } from '@/data/outageData';
import type { OutageRecord, OutageAlert, DailyOutageSummary } from '@/data/outageData';

// Map API data to frontend types
function mapOutageRecord(api: ApiOutageRecord): OutageRecord {
  return {
    id: api.id,
    date: parseISO(api.date),
    startTime: parseISO(api.start_time),
    endTime: parseISO(api.end_time),
    duration: api.duration,
    type: api.type as OutageRecord['type'],
    batteryUsed: api.battery_used,
    backupStatus: api.backup_status as OutageRecord['backupStatus'],
  };
}

function mapOutageAlert(api: ApiOutageAlert): OutageAlert {
  return {
    id: api.id,
    type: api.type as OutageAlert['type'],
    message: api.message,
    timestamp: parseISO(api.timestamp),
    read: api.read,
    priority: api.priority as OutageAlert['priority'],
  };
}

function mapDailySummary(api: ApiDailySummary, outages: OutageRecord[]): DailyOutageSummary {
  const date = parseISO(api.date);
  return {
    date,
    outageCount: api.outage_count,
    totalDuration: api.total_duration,
    outages: outages.filter(o => format(o.date, 'yyyy-MM-dd') === api.date),
  };
}

const OutagesPage = () => {
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [outageHistory, setOutageHistory] = useState<OutageRecord[]>([]);
  const [todayOutages, setTodayOutages] = useState<OutageRecord[]>([]);
  const [weekSummaries, setWeekSummaries] = useState<DailyOutageSummary[]>([]);
  const [monthlyStats, setMonthlyStats] = useState({
    totalOutages: 0,
    totalDuration: 0,
    avgDuration: 0,
    longestOutage: 0,
    totalBackupTime: 0,
    totalBatteryUsed: 0,
    hoursAvoided: 0,
  });
  const [alerts, setAlerts] = useState<OutageAlert[]>([]);
  const [gridStatus, setGridStatus] = useState({
    online: true,
    lastChange: new Date(),
    currentOutage: null as OutageRecord | null,
    batteryLevel: 0,
    estimatedBackupHours: 0,
    currentLoad: 0,
  });

  const fetchData = useCallback(async () => {
    try {
      const data = await dashboardService.getOutages(30);

      // Map outage history
      const mappedHistory = data.outage_history.map(mapOutageRecord);
      setOutageHistory(mappedHistory);

      // Map today's outages
      const mappedToday = data.today_outages.map(mapOutageRecord);
      setTodayOutages(mappedToday);

      // Map week summaries
      const mappedWeek = data.week_summaries.map(s => mapDailySummary(s, mappedHistory));
      setWeekSummaries(mappedWeek);

      // Map monthly stats
      setMonthlyStats({
        totalOutages: data.monthly_stats.total_outages,
        totalDuration: data.monthly_stats.total_duration,
        avgDuration: data.monthly_stats.avg_duration,
        longestOutage: data.monthly_stats.longest_outage,
        totalBackupTime: data.monthly_stats.total_backup_time,
        totalBatteryUsed: data.monthly_stats.total_battery_used,
        hoursAvoided: data.monthly_stats.hours_avoided,
      });

      // Map alerts
      setAlerts(data.alerts.map(mapOutageAlert));

      // Map grid status
      setGridStatus({
        online: data.grid_status.online,
        lastChange: parseISO(data.grid_status.last_change),
        currentOutage: data.grid_status.current_outage
          ? mapOutageRecord(data.grid_status.current_outage)
          : null,
        batteryLevel: data.grid_status.battery_level,
        estimatedBackupHours: data.grid_status.estimated_backup_hours,
        currentLoad: data.grid_status.current_load,
      });
    } catch {
      toast({
        title: 'Error',
        description: 'Failed to load outage data',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, [fetchData]);

  const todayDuration = todayOutages.reduce((sum, o) => sum + o.duration, 0);

  const handleExportCSV = () => {
    const csv = exportToCSV(outageHistory);
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `outage-report-${format(new Date(), 'yyyy-MM-dd')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    
    toast({
      title: 'Export Complete',
      description: 'Outage report downloaded as CSV',
    });
  };

  const handleExportPDF = () => {
    toast({
      title: 'PDF Export',
      description: 'PDF export feature coming soon',
    });
  };

  if (isLoading) {
    return (
      <AppLayout>
        <AppHeader
          title="Outage Management"
          subtitle="Track and analyze power outages"
        />
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <AppHeader
        title="Outage Management"
        subtitle="Track and analyze power outages"
      />

      <div className="p-6 space-y-6">
        {/* Top Row: Grid Status + Today Summary */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Current Grid Status - Large Indicator */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <Card className={cn(
              "h-full border-2",
              gridStatus.online 
                ? "border-success/50 bg-gradient-to-br from-success/5 to-transparent" 
                : "border-destructive/50 bg-gradient-to-br from-destructive/5 to-transparent"
            )}>
              <CardContent className="p-6 flex flex-col items-center justify-center text-center h-full min-h-[200px]">
                <motion.div
                  animate={gridStatus.online ? {} : { scale: [1, 1.1, 1] }}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                  className={cn(
                    "w-20 h-20 rounded-full flex items-center justify-center mb-4",
                    gridStatus.online ? "bg-success/20" : "bg-destructive/20"
                  )}
                >
                  {gridStatus.online ? (
                    <Zap className="w-10 h-10 text-success" />
                  ) : (
                    <ZapOff className="w-10 h-10 text-destructive animate-pulse" />
                  )}
                </motion.div>
                <h2 className={cn(
                  "text-2xl font-bold mb-2",
                  gridStatus.online ? "text-success" : "text-destructive"
                )}>
                  {gridStatus.online ? 'Grid Online' : 'Grid Offline'}
                </h2>
                <p className="text-muted-foreground text-sm">
                  {gridStatus.online 
                    ? `Last outage ended ${format(gridStatus.lastChange, 'HH:mm')}`
                    : `Outage started ${format(gridStatus.lastChange, 'HH:mm')} (${formatDuration(gridStatus.currentOutage?.duration || 0)} ago)`
                  }
                </p>
                
                {!gridStatus.online && (
                  <div className="mt-4 p-3 rounded-lg bg-background/50 border w-full">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Battery Level</span>
                      <span className="font-semibold text-battery">{gridStatus.batteryLevel}%</span>
                    </div>
                    <div className="flex items-center justify-between text-sm mt-2">
                      <span className="text-muted-foreground">Est. Backup Time</span>
                      <span className="font-semibold text-info">{gridStatus.estimatedBackupHours}h</span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>

          {/* Today's Summary */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="lg:col-span-2"
          >
            <Card className="h-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Calendar className="h-5 w-5 text-primary" />
                  Today's Outages
                </CardTitle>
                <CardDescription>
                  {format(new Date(), 'EEEE, MMMM d, yyyy')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Summary stats */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg bg-muted/50">
                    <div className="flex items-center gap-2 text-muted-foreground mb-1">
                      <AlertTriangle className="h-4 w-4" />
                      <span className="text-sm">Outage Count</span>
                    </div>
                    <p className="text-3xl font-bold text-foreground">
                      {todayOutages.length}
                    </p>
                  </div>
                  <div className="p-4 rounded-lg bg-muted/50">
                    <div className="flex items-center gap-2 text-muted-foreground mb-1">
                      <Clock className="h-4 w-4" />
                      <span className="text-sm">Total Duration</span>
                    </div>
                    <p className="text-3xl font-bold text-foreground">
                      {formatDuration(todayDuration)}
                    </p>
                  </div>
                </div>

                {/* Timeline */}
                <Separator />
                <OutageTimeline outages={todayOutages} />
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Weekly Calendar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-primary" />
                This Week
              </CardTitle>
              <CardDescription>
                Outage frequency and duration by day
              </CardDescription>
            </CardHeader>
            <CardContent>
              <OutageCalendar summaries={weekSummaries} />
            </CardContent>
          </Card>
        </motion.div>

        {/* Monthly Statistics */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary" />
              Monthly Statistics
            </h2>
            <span className="text-sm text-muted-foreground">
              {format(new Date(), 'MMMM yyyy')}
            </span>
          </div>
          <OutageStatsCards stats={monthlyStats} />
        </motion.div>

        {/* Tabs: History & Alerts */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <Tabs defaultValue="history" className="space-y-4">
            <div className="flex items-center justify-between">
              <TabsList>
                <TabsTrigger value="history" className="gap-2">
                  <FileSpreadsheet className="h-4 w-4" />
                  Outage History
                </TabsTrigger>
                <TabsTrigger value="alerts" className="gap-2">
                  <Bell className="h-4 w-4" />
                  Alerts
                </TabsTrigger>
              </TabsList>

              {/* Export Buttons */}
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleExportCSV}>
                  <Download className="h-4 w-4 mr-2" />
                  CSV
                </Button>
                <Button variant="outline" size="sm" onClick={handleExportPDF}>
                  <Download className="h-4 w-4 mr-2" />
                  PDF
                </Button>
              </div>
            </div>

            <TabsContent value="history">
              <Card>
                <CardHeader>
                  <CardTitle>Outage History</CardTitle>
                  <CardDescription>
                    Complete log of all recorded power outages
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <OutageHistoryTable outages={outageHistory} />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="alerts">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Bell className="h-5 w-5 text-primary" />
                    Outage Alerts
                  </CardTitle>
                  <CardDescription>
                    Notifications about grid status and battery backup
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <OutageAlertsPanel alerts={alerts} />

                  {/* Battery Prediction Widget */}
                  <Separator className="my-4" />
                  <div className="p-4 rounded-lg bg-info/10 border border-info/20">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-full bg-info/20">
                        <Battery className="h-5 w-5 text-info" />
                      </div>
                      <div>
                        <p className="font-medium text-foreground">Battery Backup Prediction</p>
                        <p className="text-sm text-muted-foreground">
                          At current load ({gridStatus.currentLoad} kW), battery will last
                        </p>
                      </div>
                      <div className="ml-auto text-right">
                        <p className="text-2xl font-bold text-info">
                          {gridStatus.estimatedBackupHours}
                        </p>
                        <p className="text-xs text-muted-foreground">hours</p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </motion.div>
      </div>
    </AppLayout>
  );
};

export default OutagesPage;
