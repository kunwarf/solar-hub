import { motion } from "framer-motion";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

interface TelemetryData {
  id: string;
  timestamp: string;
  parameter: string;
  value: string;
  unit: string;
  status: "normal" | "warning" | "critical";
}

interface TelemetryTableProps {
  data: TelemetryData[];
  title: string;
}

const statusStyles = {
  normal: "text-success",
  warning: "text-warning",
  critical: "text-destructive",
};

export function TelemetryTable({ data, title }: TelemetryTableProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card overflow-hidden"
    >
      <div className="p-4 border-b border-border">
        <h3 className="text-lg font-semibold text-foreground">{title}</h3>
      </div>
      
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent">
              <TableHead className="text-muted-foreground">Timestamp</TableHead>
              <TableHead className="text-muted-foreground">Parameter</TableHead>
              <TableHead className="text-muted-foreground text-right">Value</TableHead>
              <TableHead className="text-muted-foreground text-center">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row, index) => (
              <motion.tr
                key={row.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className="border-border hover:bg-secondary/30"
              >
                <TableCell className="font-mono text-sm text-muted-foreground">
                  {row.timestamp}
                </TableCell>
                <TableCell className="text-foreground">{row.parameter}</TableCell>
                <TableCell className="text-right">
                  <span className="font-mono text-foreground">{row.value}</span>
                  <span className="text-muted-foreground ml-1">{row.unit}</span>
                </TableCell>
                <TableCell className="text-center">
                  <span className={cn("font-medium capitalize", statusStyles[row.status])}>
                    {row.status}
                  </span>
                </TableCell>
              </motion.tr>
            ))}
          </TableBody>
        </Table>
      </div>
    </motion.div>
  );
}
