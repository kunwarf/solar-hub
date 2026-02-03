/**
 * ⚠️ WARNING: DEMO PAGE WITH MOCK DATA ⚠️
 *
 * This page uses HARDCODED VALUES for demonstration:
 * - System cost: Rs. 850,000
 * - Install date: 2023-06-15
 * - Monthly savings: Rs. 12,500
 * - Degradation rate: 0.5% per year
 * - Inflation rate: 10% per year
 * - All financial projections are simulated with Math.random() variance
 *
 * TODO: Replace with real billing data integration
 * - Connect to actual billing history API
 * - Use real tariff plans for calculations
 * - Fetch actual system installation details from site configuration
 * - Calculate savings from real net metering data
 */

import { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { format, differenceInMonths, differenceInDays, addMonths, addYears } from 'date-fns';
import {
  TrendingUp,
  Calendar,
  PiggyBank,
  Target,
  Smartphone,
  Bike,
  Receipt,
  Sun,
  Edit2,
  Check,
  Trophy,
  Zap,
  BarChart3,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ComposedChart,
  Area,
} from 'recharts';
import { AppLayout } from '@/components/layout/AppLayout';
import { AppHeader } from '@/components/layout/AppHeader';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { AnimatedCounter } from '@/components/savings/AnimatedCounter';
import { AchievementBadge, SAVINGS_ACHIEVEMENTS } from '@/components/savings/AchievementBadge';
import { cn } from '@/lib/utils';

// Mock data for savings
const generateMonthlySavings = (installDate: Date, avgMonthlySavings: number) => {
  const months = differenceInMonths(new Date(), installDate);
  const data = [];
  let cumulative = 0;
  
  for (let i = 0; i <= months; i++) {
    const monthDate = addMonths(installDate, i);
    // Add some variance to monthly savings
    const variance = (Math.random() - 0.5) * 0.3; // ±15%
    const savings = Math.round(avgMonthlySavings * (1 + variance));
    cumulative += savings;
    
    data.push({
      month: format(monthDate, 'MMM yy'),
      savings,
      cumulative,
    });
  }
  
  return data;
};

const SavingsPage = () => {
  // Editable investment details
  const [isEditing, setIsEditing] = useState(false);
  const [systemCost, setSystemCost] = useState(850000);
  const [installDate, setInstallDate] = useState(new Date('2023-06-15'));
  const [systemCapacity, setSystemCapacity] = useState(10);
  
  // Derived calculations
  const avgMonthlySavings = 12500; // Rs per month average
  const monthsSinceInstall = differenceInMonths(new Date(), installDate);
  const daysSinceInstall = differenceInDays(new Date(), installDate);
  
  const monthlySavingsData = useMemo(
    () => generateMonthlySavings(installDate, avgMonthlySavings),
    [installDate, avgMonthlySavings]
  );
  
  const lifetimeSavings = monthlySavingsData[monthlySavingsData.length - 1]?.cumulative || 0;
  const breakEvenProgress = Math.min(100, (lifetimeSavings / systemCost) * 100);
  const remainingToBreakeven = Math.max(0, systemCost - lifetimeSavings);
  const monthsToBreakeven = remainingToBreakeven > 0 
    ? Math.ceil(remainingToBreakeven / avgMonthlySavings) 
    : 0;
  const breakEvenDate = addMonths(new Date(), monthsToBreakeven);
  
  // Fun equivalents
  const equivalentMonthsBills = Math.round(lifetimeSavings / 15000); // Assuming Rs 15k avg bill
  const equivalentIphones = Math.round(lifetimeSavings / 350000); // iPhone 15 Pro price
  const equivalentMotorbikes = Math.round(lifetimeSavings / 180000); // Honda 125 price
  
  // Projections with degradation and inflation
  const projections = useMemo(() => {
    const degradationRate = 0.005; // 0.5% per year
    const inflationRate = 0.10; // 10% annual tariff increase
    const yearsToProject = [1, 5, 10, 25];
    
    return yearsToProject.map(years => {
      let totalSavings = lifetimeSavings;
      let currentYearlySavings = avgMonthlySavings * 12;
      
      for (let y = 0; y < years; y++) {
        // Apply degradation and inflation
        const effectiveMultiplier = Math.pow(1 - degradationRate, y) * Math.pow(1 + inflationRate, y);
        totalSavings += currentYearlySavings * effectiveMultiplier;
      }
      
      return {
        years,
        totalSavings: Math.round(totalSavings),
        yearlyAtEnd: Math.round(currentYearlySavings * Math.pow(1 - degradationRate, years) * Math.pow(1 + inflationRate, years)),
      };
    });
  }, [lifetimeSavings, avgMonthlySavings]);
  
  // Chart data with projection
  const chartDataWithProjection = useMemo(() => {
    const data = [...monthlySavingsData];
    
    // Add projection months until breakeven
    if (remainingToBreakeven > 0) {
      let projected = lifetimeSavings;
      for (let i = 1; i <= monthsToBreakeven + 3; i++) {
        projected += avgMonthlySavings;
        data.push({
          month: format(addMonths(new Date(), i), 'MMM yy'),
          savings: 0,
          cumulative: 0,
          projected,
          isProjection: true,
        });
      }
    }
    
    // Add breakeven line
    return data.map(d => ({
      ...d,
      breakeven: systemCost,
    }));
  }, [monthlySavingsData, remainingToBreakeven, monthsToBreakeven, avgMonthlySavings, systemCost, lifetimeSavings]);

  const formatCurrency = (amount: number) => {
    if (amount >= 10000000) {
      return `Rs. ${(amount / 10000000).toFixed(2)} Cr`;
    }
    if (amount >= 100000) {
      return `Rs. ${(amount / 100000).toFixed(2)} Lac`;
    }
    return `Rs. ${amount.toLocaleString('en-PK')}`;
  };

  return (
    <AppLayout>
      <AppHeader 
        title="ROI & Savings Dashboard" 
        subtitle="Track your solar investment returns"
      />

      <div className="p-6 space-y-6">
        {/* Investment Summary Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Sun className="h-5 w-5 text-solar" />
                    Investment Summary
                  </CardTitle>
                  <CardDescription>Your solar system details</CardDescription>
                </div>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => setIsEditing(!isEditing)}
                >
                  {isEditing ? <Check className="h-4 w-4" /> : <Edit2 className="h-4 w-4" />}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="space-y-2">
                  <Label>Total System Cost</Label>
                  {isEditing ? (
                    <Input
                      type="number"
                      value={systemCost}
                      onChange={(e) => setSystemCost(parseInt(e.target.value) || 0)}
                      className="font-mono"
                    />
                  ) : (
                    <p className="text-2xl font-bold text-foreground font-mono">
                      Rs. {systemCost.toLocaleString()}
                    </p>
                  )}
                </div>
                
                <div className="space-y-2">
                  <Label>Installation Date</Label>
                  {isEditing ? (
                    <Input
                      type="date"
                      value={format(installDate, 'yyyy-MM-dd')}
                      onChange={(e) => setInstallDate(new Date(e.target.value))}
                    />
                  ) : (
                    <div className="flex items-center gap-2">
                      <Calendar className="h-5 w-5 text-muted-foreground" />
                      <p className="text-lg font-medium">
                        {format(installDate, 'MMM d, yyyy')}
                      </p>
                    </div>
                  )}
                  <p className="text-sm text-muted-foreground">
                    {monthsSinceInstall} months ago ({daysSinceInstall} days)
                  </p>
                </div>
                
                <div className="space-y-2">
                  <Label>System Capacity</Label>
                  {isEditing ? (
                    <Input
                      type="number"
                      value={systemCapacity}
                      onChange={(e) => setSystemCapacity(parseFloat(e.target.value) || 0)}
                      className="font-mono"
                    />
                  ) : (
                    <div className="flex items-center gap-2">
                      <Zap className="h-5 w-5 text-solar" />
                      <p className="text-2xl font-bold text-foreground">
                        {systemCapacity} kW
                      </p>
                    </div>
                  )}
                  <p className="text-sm text-muted-foreground">
                    ~{Math.round(systemCapacity * 120)} kWh/month generation
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Lifetime Savings Counter */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="bg-gradient-to-br from-success/10 via-success/5 to-transparent border-success/30">
            <CardContent className="py-8">
              <div className="text-center space-y-4">
                <div className="flex items-center justify-center gap-2">
                  <PiggyBank className="h-8 w-8 text-success" />
                  <h2 className="text-xl font-semibold text-muted-foreground">Total Lifetime Savings</h2>
                </div>
                
                <div className="text-5xl md:text-6xl font-bold text-success font-mono">
                  <AnimatedCounter 
                    value={lifetimeSavings} 
                    prefix="Rs. "
                    duration={2}
                  />
                </div>
                
                <Separator className="my-6" />
                
                {/* Fun Equivalents */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.5 }}
                    className="p-4 rounded-lg bg-background/50 border"
                  >
                    <div className="flex items-center justify-center gap-2 text-muted-foreground mb-2">
                      <Receipt className="h-5 w-5" />
                      <span className="text-sm">Equivalent to</span>
                    </div>
                    <p className="text-2xl font-bold text-foreground">{equivalentMonthsBills}</p>
                    <p className="text-sm text-muted-foreground">months of electricity bills</p>
                  </motion.div>
                  
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.6 }}
                    className="p-4 rounded-lg bg-background/50 border"
                  >
                    <div className="flex items-center justify-center gap-2 text-muted-foreground mb-2">
                      <Smartphone className="h-5 w-5" />
                      <span className="text-sm">Or about</span>
                    </div>
                    <p className="text-2xl font-bold text-foreground">{equivalentIphones || '<1'}</p>
                    <p className="text-sm text-muted-foreground">iPhone 15 Pro units</p>
                  </motion.div>
                  
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.7 }}
                    className="p-4 rounded-lg bg-background/50 border"
                  >
                    <div className="flex items-center justify-center gap-2 text-muted-foreground mb-2">
                      <Bike className="h-5 w-5" />
                      <span className="text-sm">Or even</span>
                    </div>
                    <p className="text-2xl font-bold text-foreground">{equivalentMotorbikes || '<1'}</p>
                    <p className="text-sm text-muted-foreground">Honda 125 motorbikes</p>
                  </motion.div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Break-even Progress */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5 text-primary" />
                Break-even Progress
              </CardTitle>
              <CardDescription>Track your journey to ROI</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Progress</span>
                  <span className="text-lg font-bold text-primary">
                    {breakEvenProgress.toFixed(1)}%
                  </span>
                </div>
                <div className="relative">
                  <Progress value={breakEvenProgress} className="h-4" />
                  {breakEvenProgress >= 100 && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="absolute -right-2 -top-2"
                    >
                      <Trophy className="h-8 w-8 text-amber-500" />
                    </motion.div>
                  )}
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Rs. 0</span>
                  <span>Rs. {systemCost.toLocaleString()}</span>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-muted/50 text-center">
                  <p className="text-sm text-muted-foreground">Already Saved</p>
                  <p className="text-xl font-bold text-success font-mono">
                    Rs. {lifetimeSavings.toLocaleString()}
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-muted/50 text-center">
                  <p className="text-sm text-muted-foreground">Remaining</p>
                  <p className="text-xl font-bold text-foreground font-mono">
                    Rs. {remainingToBreakeven.toLocaleString()}
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-primary/10 text-center border border-primary/20">
                  <p className="text-sm text-muted-foreground">Estimated Break-even</p>
                  <p className="text-xl font-bold text-primary">
                    {breakEvenProgress >= 100 ? 'Achieved! 🎉' : format(breakEvenDate, 'MMM yyyy')}
                  </p>
                  {breakEvenProgress < 100 && (
                    <p className="text-xs text-muted-foreground mt-1">
                      ~{monthsToBreakeven} months remaining
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Monthly Savings Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-primary" />
                Savings History & Projection
              </CardTitle>
              <CardDescription>Monthly savings with cumulative progress toward break-even</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[350px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartDataWithProjection} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis 
                      dataKey="month" 
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis 
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '8px',
                      }}
                      formatter={(value: number, name: string) => [
                        `Rs. ${value.toLocaleString()}`,
                        name === 'savings' ? 'Monthly Savings' :
                        name === 'cumulative' ? 'Total Saved' :
                        name === 'projected' ? 'Projected' :
                        name === 'breakeven' ? 'Break-even Target' : name
                      ]}
                    />
                    <Legend />
                    <Bar 
                      dataKey="savings" 
                      name="Monthly Savings"
                      fill="hsl(var(--success))" 
                      radius={[4, 4, 0, 0]}
                    />
                    <Line 
                      type="monotone"
                      dataKey="cumulative" 
                      name="Total Saved"
                      stroke="hsl(var(--primary))"
                      strokeWidth={3}
                      dot={false}
                    />
                    <Line 
                      type="monotone"
                      dataKey="projected" 
                      name="Projected"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      dot={false}
                    />
                    <Line 
                      type="monotone"
                      dataKey="breakeven" 
                      name="Break-even"
                      stroke="hsl(var(--destructive))"
                      strokeWidth={2}
                      strokeDasharray="10 5"
                      dot={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Projections Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-primary" />
                Long-term Projections
              </CardTitle>
              <CardDescription>
                Accounting for 0.5% annual panel degradation and 10% tariff inflation
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Time Period</TableHead>
                      <TableHead className="text-right">Projected Total Savings</TableHead>
                      <TableHead className="text-right">Annual Savings (at end)</TableHead>
                      <TableHead className="text-right">ROI Multiple</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {projections.map((proj) => (
                      <TableRow key={proj.years}>
                        <TableCell className="font-medium">
                          {proj.years} Year{proj.years > 1 ? 's' : ''}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          <span className="text-success font-semibold">
                            {formatCurrency(proj.totalSavings)}
                          </span>
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          Rs. {proj.yearlyAtEnd.toLocaleString()}/yr
                        </TableCell>
                        <TableCell className="text-right">
                          <Badge variant={proj.totalSavings > systemCost ? 'default' : 'secondary'}>
                            {(proj.totalSavings / systemCost).toFixed(1)}x
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              
              <div className="mt-4 p-4 rounded-lg bg-muted/50 text-sm text-muted-foreground">
                <p>
                  <strong>Note:</strong> Projections assume 0.5% annual panel efficiency degradation 
                  and 10% annual electricity tariff increase. Actual results may vary based on 
                  weather, maintenance, and regulatory changes.
                </p>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Achievement Badges */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trophy className="h-5 w-5 text-amber-500" />
                Achievements
              </CardTitle>
              <CardDescription>
                Milestones on your solar journey
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
                {SAVINGS_ACHIEVEMENTS.map((achievement, index) => (
                  <AchievementBadge 
                    key={achievement.id} 
                    achievement={achievement}
                    index={index}
                  />
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </AppLayout>
  );
};

export default SavingsPage;
