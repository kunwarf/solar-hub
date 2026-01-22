// Mock outage data with realistic Pakistani load shedding patterns
import { format, subDays, addHours, addMinutes, differenceInMinutes, startOfDay, isToday, isSameDay } from 'date-fns';

export type OutageType = 'scheduled' | 'unscheduled' | 'unknown';
export type BackupStatus = 'full' | 'partial' | 'none';

export interface OutageRecord {
  id: string;
  date: Date;
  startTime: Date;
  endTime: Date;
  duration: number; // in minutes
  type: OutageType;
  batteryUsed: number; // kWh
  backupStatus: BackupStatus;
}

export interface OutageAlert {
  id: string;
  type: 'grid_down' | 'grid_restored' | 'low_battery' | 'battery_critical' | 'prediction';
  message: string;
  timestamp: Date;
  read: boolean;
  priority: 'low' | 'medium' | 'high' | 'critical';
}

export interface DailyOutageSummary {
  date: Date;
  outageCount: number;
  totalDuration: number; // minutes
  outages: OutageRecord[];
}

// Generate realistic Pakistani load shedding patterns
// Summer months (May-Sept): 3-4 outages, 2-4 hours each
// Winter months: 1-2 outages, 1-2 hours each
function generateOutagePattern(date: Date): OutageRecord[] {
  const month = date.getMonth();
  const isSummer = month >= 4 && month <= 8;
  
  const outages: OutageRecord[] = [];
  const numOutages = isSummer 
    ? Math.floor(Math.random() * 3) + 2 // 2-4 outages
    : Math.floor(Math.random() * 2) + 1; // 1-2 outages
  
  // Typical outage times in Pakistan
  const typicalSlots = [
    { start: 6, duration: 120 },   // Early morning 6-8 AM
    { start: 10, duration: 150 },  // Mid-morning 10 AM - 12:30 PM
    { start: 14, duration: 180 },  // Afternoon 2-5 PM (peak)
    { start: 18, duration: 120 },  // Evening 6-8 PM
    { start: 22, duration: 90 },   // Night 10-11:30 PM
  ];

  const usedSlots = new Set<number>();
  
  for (let i = 0; i < numOutages; i++) {
    let slotIndex: number;
    do {
      slotIndex = Math.floor(Math.random() * typicalSlots.length);
    } while (usedSlots.has(slotIndex));
    usedSlots.add(slotIndex);
    
    const slot = typicalSlots[slotIndex];
    const baseStart = startOfDay(date);
    const startTime = addHours(addMinutes(baseStart, Math.random() * 30), slot.start);
    
    // Duration varies: 60-180 minutes for summer, 30-120 for winter
    const duration = isSummer
      ? Math.floor(Math.random() * 120) + 60
      : Math.floor(Math.random() * 90) + 30;
    
    const endTime = addMinutes(startTime, duration);
    
    // Battery usage: roughly 0.5-1.5 kWh per hour
    const batteryUsed = (duration / 60) * (0.5 + Math.random());
    
    // Backup status based on battery capacity and outage duration
    let backupStatus: BackupStatus = 'full';
    if (duration > 180) backupStatus = 'partial';
    if (duration > 300) backupStatus = 'none';
    if (Math.random() < 0.1) backupStatus = 'partial'; // 10% chance of partial
    
    // Type: 70% scheduled, 20% unscheduled, 10% unknown
    const typeRand = Math.random();
    let type: OutageType = 'scheduled';
    if (typeRand > 0.9) type = 'unknown';
    else if (typeRand > 0.7) type = 'unscheduled';
    
    outages.push({
      id: `outage-${date.getTime()}-${i}`,
      date,
      startTime,
      endTime,
      duration,
      type,
      batteryUsed: Math.round(batteryUsed * 100) / 100,
      backupStatus,
    });
  }
  
  return outages.sort((a, b) => a.startTime.getTime() - b.startTime.getTime());
}

// Generate historical data for the past 30 days
export function generateOutageHistory(days: number = 30): OutageRecord[] {
  const allOutages: OutageRecord[] = [];
  const today = new Date();
  
  for (let i = 0; i < days; i++) {
    const date = subDays(today, i);
    // 80% chance of outages on any given day
    if (Math.random() < 0.8 || i === 0) {
      allOutages.push(...generateOutagePattern(date));
    }
  }
  
  return allOutages.sort((a, b) => b.startTime.getTime() - a.startTime.getTime());
}

// Get today's outages
export function getTodayOutages(history: OutageRecord[]): OutageRecord[] {
  const today = new Date();
  return history.filter(outage => isToday(outage.date));
}

// Get this week's daily summaries
export function getWeekSummaries(history: OutageRecord[]): DailyOutageSummary[] {
  const summaries: DailyOutageSummary[] = [];
  
  for (let i = 0; i < 7; i++) {
    const date = subDays(new Date(), i);
    const dayOutages = history.filter(o => isSameDay(o.date, date));
    
    summaries.push({
      date,
      outageCount: dayOutages.length,
      totalDuration: dayOutages.reduce((sum, o) => sum + o.duration, 0),
      outages: dayOutages,
    });
  }
  
  return summaries;
}

// Calculate monthly statistics
export function getMonthlyStats(history: OutageRecord[]) {
  const now = new Date();
  const currentMonth = now.getMonth();
  const currentYear = now.getFullYear();
  
  const monthOutages = history.filter(o => {
    const d = new Date(o.date);
    return d.getMonth() === currentMonth && d.getFullYear() === currentYear;
  });
  
  const totalOutages = monthOutages.length;
  const totalDuration = monthOutages.reduce((sum, o) => sum + o.duration, 0);
  const avgDuration = totalOutages > 0 ? Math.round(totalDuration / totalOutages) : 0;
  const longestOutage = monthOutages.reduce((max, o) => Math.max(max, o.duration), 0);
  const totalBackupTime = monthOutages
    .filter(o => o.backupStatus !== 'none')
    .reduce((sum, o) => sum + o.duration, 0);
  const totalBatteryUsed = monthOutages.reduce((sum, o) => sum + o.batteryUsed, 0);
  
  // "Hours of darkness avoided" = backup time provided
  const hoursAvoided = Math.round(totalBackupTime / 60 * 10) / 10;
  
  return {
    totalOutages,
    totalDuration,
    avgDuration,
    longestOutage,
    totalBackupTime,
    totalBatteryUsed: Math.round(totalBatteryUsed * 10) / 10,
    hoursAvoided,
  };
}

// Generate mock alerts
export function generateOutageAlerts(): OutageAlert[] {
  const now = new Date();
  
  return [
    {
      id: 'alert-1',
      type: 'grid_restored',
      message: 'Grid power restored after 2h 15m outage',
      timestamp: subDays(now, 0),
      read: false,
      priority: 'low',
    },
    {
      id: 'alert-2',
      type: 'prediction',
      message: 'Battery will last 4.2 more hours at current load',
      timestamp: subDays(now, 0),
      read: false,
      priority: 'medium',
    },
    {
      id: 'alert-3',
      type: 'grid_down',
      message: 'Grid power lost - switching to battery backup',
      timestamp: subDays(addHours(now, -3), 0),
      read: true,
      priority: 'high',
    },
    {
      id: 'alert-4',
      type: 'low_battery',
      message: 'Battery at 25% during outage - consider reducing load',
      timestamp: subDays(now, 1),
      read: true,
      priority: 'high',
    },
    {
      id: 'alert-5',
      type: 'battery_critical',
      message: 'Battery critical at 10% - grid power needed soon',
      timestamp: subDays(now, 2),
      read: true,
      priority: 'critical',
    },
  ];
}

// Current grid status
export interface GridStatus {
  online: boolean;
  lastChange: Date;
  currentOutage: OutageRecord | null;
  batteryLevel: number;
  estimatedBackupHours: number;
  currentLoad: number; // kW
}

export function getCurrentGridStatus(): GridStatus {
  // Simulate grid being online most of the time
  const online = Math.random() > 0.15; // 85% chance online
  
  return {
    online,
    lastChange: online ? subDays(new Date(), 0) : addMinutes(new Date(), -45),
    currentOutage: online ? null : {
      id: 'current',
      date: new Date(),
      startTime: addMinutes(new Date(), -45),
      endTime: new Date(), // ongoing
      duration: 45,
      type: 'unscheduled',
      batteryUsed: 0.8,
      backupStatus: 'full',
    },
    batteryLevel: 72,
    estimatedBackupHours: 4.2,
    currentLoad: 2.1,
  };
}

// Format duration in human readable format
export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  
  if (hours === 0) return `${mins}m`;
  if (mins === 0) return `${hours}h`;
  return `${hours}h ${mins}m`;
}

// Export outage data as CSV
export function exportToCSV(outages: OutageRecord[]): string {
  const headers = ['Date', 'Start Time', 'End Time', 'Duration', 'Type', 'Battery Used (kWh)', 'Backup Status'];
  
  const rows = outages.map(o => [
    format(o.date, 'yyyy-MM-dd'),
    format(o.startTime, 'HH:mm'),
    format(o.endTime, 'HH:mm'),
    formatDuration(o.duration),
    o.type,
    o.batteryUsed.toFixed(2),
    o.backupStatus,
  ]);
  
  return [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
}
