import { useState } from 'react';
import { format } from 'date-fns';
import { OutageRecord, formatDuration } from '@/data/outageData';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface OutageHistoryTableProps {
  outages: OutageRecord[];
  className?: string;
}

const ITEMS_PER_PAGE = 10;

export function OutageHistoryTable({ outages, className }: OutageHistoryTableProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState<string>('all');

  const filteredOutages = typeFilter === 'all' 
    ? outages 
    : outages.filter(o => o.type === typeFilter);

  const totalPages = Math.ceil(filteredOutages.length / ITEMS_PER_PAGE);
  const paginatedOutages = filteredOutages.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  const getTypeBadgeVariant = (type: string) => {
    switch (type) {
      case 'scheduled': return 'destructive';
      case 'unscheduled': return 'secondary';
      default: return 'outline';
    }
  };

  const getBackupBadgeColor = (status: string) => {
    switch (status) {
      case 'full': return 'bg-success/20 text-success border-success/30';
      case 'partial': return 'bg-warning/20 text-warning border-warning/30';
      case 'none': return 'bg-destructive/20 text-destructive border-destructive/30';
      default: return '';
    }
  };

  return (
    <div className={cn("space-y-4", className)}>
      {/* Filters */}
      <div className="flex items-center justify-between">
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter by type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="scheduled">Scheduled</SelectItem>
            <SelectItem value="unscheduled">Unscheduled</SelectItem>
            <SelectItem value="unknown">Unknown</SelectItem>
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">
          {filteredOutages.length} outages
        </span>
      </div>

      {/* Table */}
      <div className="rounded-lg border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Start</TableHead>
              <TableHead>End</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Type</TableHead>
              <TableHead className="text-right">Battery Used</TableHead>
              <TableHead>Backup Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedOutages.map((outage) => (
              <TableRow key={outage.id}>
                <TableCell className="font-medium">
                  {format(outage.date, 'MMM d, yyyy')}
                </TableCell>
                <TableCell className="font-mono">
                  {format(outage.startTime, 'HH:mm')}
                </TableCell>
                <TableCell className="font-mono">
                  {format(outage.endTime, 'HH:mm')}
                </TableCell>
                <TableCell>
                  {formatDuration(outage.duration)}
                </TableCell>
                <TableCell>
                  <Badge variant={getTypeBadgeVariant(outage.type)} className="capitalize">
                    {outage.type}
                  </Badge>
                </TableCell>
                <TableCell className="text-right font-mono">
                  {outage.batteryUsed.toFixed(2)} kWh
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className={cn("capitalize", getBackupBadgeColor(outage.backupStatus))}>
                    {outage.backupStatus}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            Page {currentPage} of {totalPages}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
