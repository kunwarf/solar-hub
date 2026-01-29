import { memo } from "react";
import { motion } from "framer-motion";
import { Sun, Home, Zap, Grid3X3 } from "lucide-react";
import LiveIndicator from "./LiveIndicator";
import ConnectionStatusIndicator from "./ConnectionStatusIndicator";

interface EnergyFlowDiagramProps {
  solarPower: number;
  batteryPower: number;
  batteryLevel: number;
  consumption: number;
  gridPower: number;
  isGridExporting: boolean;
  showConnectionStatus?: boolean;
}

// Animated particle using SMIL
const AnimatedParticle = ({
  pathId,
  color,
  duration,
  delay,
  size = 6,
}: {
  pathId: string;
  color: string;
  duration: number;
  delay: number;
  size?: number;
}) => {
  return (
    <circle r={size} fill={color} filter="url(#particleGlow)">
      <animateMotion
        dur={`${duration}s`}
        repeatCount="indefinite"
        begin={`${delay}s`}
      >
        <mpath href={`#${pathId}`} />
      </animateMotion>
    </circle>
  );
};

// Flow connection with animated particles
const FlowConnection = ({
  pathId,
  path,
  color,
  power,
  reverse = false,
}: {
  pathId: string;
  path: string;
  color: string;
  power: number;
  reverse?: boolean;
}) => {
  if (power === 0) return null;

  const absPower = Math.abs(power);
  const particleCount = Math.min(Math.max(Math.ceil(absPower / 2), 2), 5);
  const duration = Math.max(1, 2.5 - absPower * 0.15);
  const actualPath = reverse ? reversePath(path) : path;

  return (
    <g>
      {/* Base path */}
      <path
        id={pathId}
        d={actualPath}
        fill="none"
        stroke={color}
        strokeWidth="3"
        strokeOpacity="0.15"
        strokeLinecap="round"
      />
      {/* Glowing overlay */}
      <path
        d={actualPath}
        fill="none"
        stroke={color}
        strokeWidth="4"
        strokeOpacity="0.4"
        strokeLinecap="round"
        filter="url(#lineGlow)"
      />
      {/* Animated particles */}
      {Array.from({ length: particleCount }).map((_, i) => (
        <AnimatedParticle
          key={i}
          pathId={pathId}
          color={color}
          duration={duration}
          delay={(i * duration) / particleCount}
          size={6 + Math.min(absPower * 0.4, 4)}
        />
      ))}
    </g>
  );
};

// Helper to reverse SVG path for opposite direction
const reversePath = (path: string): string => {
  const parts = path.match(/M\s*([\d.]+)\s+([\d.]+)\s*Q\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)/);
  if (parts) {
    const [, x1, y1, cx, cy, x2, y2] = parts;
    return `M ${x2} ${y2} Q ${cx} ${cy} ${x1} ${y1}`;
  }
  return path;
};

// Dynamic Battery Node with fill level
const BatteryNode = ({
  level,
  power,
  position,
  delay = 0,
}: {
  level: number;
  power: number;
  position: { x: number; y: number };
  delay?: number;
}) => {
  const { x, y } = position;
  const isCharging = power > 0;
  const isDischarging = power < 0;
  const fillHeight = Math.max(0, Math.min(100, level));
  const size = 72; // Larger node size
  
  const getFillColor = () => {
    if (level >= 60) return "#10B981";
    if (level >= 30) return "#F59E0B";
    return "#EF4444";
  };

  return (
    <motion.g
      initial={{ opacity: 0, scale: 0.5 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay, duration: 0.4, ease: "backOut" }}
    >
      {/* Active pulse when charging/discharging */}
      {(isCharging || isDischarging) && (
        <circle cx={x} cy={y} r={size / 2 + 8} fill="none" stroke={getFillColor()} strokeWidth="2" strokeOpacity="0.4">
          <animate attributeName="r" values={`${size / 2 + 8};${size / 2 + 16};${size / 2 + 8}`} dur="2s" repeatCount="indefinite" />
          <animate attributeName="stroke-opacity" values="0.4;0.1;0.4" dur="2s" repeatCount="indefinite" />
        </circle>
      )}
      
      {/* Node background */}
      <circle
        cx={x}
        cy={y}
        r={size / 2}
        fill={`${getFillColor()}20`}
        stroke={getFillColor()}
        strokeWidth="3"
        strokeOpacity="0.6"
      />
      
      {/* Battery icon with fill */}
      <g transform={`translate(${x - 14}, ${y - 20})`}>
        {/* Battery terminal */}
        <rect x="8" y="0" width="12" height="5" rx="1.5" fill="currentColor" opacity="0.5" className="fill-muted-foreground" />
        {/* Battery body */}
        <rect x="2" y="5" width="24" height="34" rx="3" fill="none" stroke={getFillColor()} strokeWidth="2.5" />
        {/* Battery fill */}
        <rect
          x="5"
          y={9 + (26 * (1 - fillHeight / 100))}
          width="18"
          height={26 * (fillHeight / 100)}
          rx="2"
          fill={getFillColor()}
          opacity="0.8"
        >
          {isCharging && (
            <animate attributeName="opacity" values="0.6;0.9;0.6" dur="1s" repeatCount="indefinite" />
          )}
        </rect>
        {/* Charging bolt */}
        {isCharging && (
          <path
            d="M15 12L10 22H14L12 30L18 20H14L15 12Z"
            fill="hsl(var(--background))"
            stroke="hsl(var(--background))"
            strokeWidth="0.5"
          />
        )}
      </g>
      
      {/* Label */}
      <text
        x={x}
        y={y + size / 2 + 24}
        textAnchor="middle"
        className="text-base fill-muted-foreground font-medium"
      >
        Battery
      </text>

      {/* SOC Value - moved up slightly */}
      <text
        x={x}
        y={y + size / 2 + 45}
        textAnchor="middle"
        className="font-mono text-sm font-medium"
        fill={getFillColor()}
      >
        {level}%
      </text>

      {/* Power Value - added below SOC */}
      <text
        x={x}
        y={y + size / 2 + 65}
        textAnchor="middle"
        className="font-mono text-xl font-bold"
        fill={isCharging ? "#10B981" : isDischarging ? "#F59E0B" : getFillColor()}
      >
        {Math.abs(power).toFixed(1)} kW {isCharging ? "↑" : isDischarging ? "↓" : ""}
      </text>
    </motion.g>
  );
};

// Energy node component - minimal with larger labels
const EnergyNode = ({
  icon: Icon,
  label,
  value,
  unit,
  color,
  position,
  isActive = false,
  delay = 0,
  labelPosition = "below",
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  unit: string;
  color: string;
  position: { x: number; y: number };
  isActive?: boolean;
  delay?: number;
  labelPosition?: "above" | "below";
}) => {
  const size = 72; // Larger node size
  const { x, y } = position;

  return (
    <motion.g
      initial={{ opacity: 0, scale: 0.5 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay, duration: 0.4, ease: "backOut" }}
    >
      {/* Active pulse ring */}
      {isActive && (
        <circle cx={x} cy={y} r={size / 2 + 8} fill="none" stroke={color} strokeWidth="2" strokeOpacity="0.4">
          <animate attributeName="r" values={`${size / 2 + 8};${size / 2 + 16};${size / 2 + 8}`} dur="2s" repeatCount="indefinite" />
          <animate attributeName="stroke-opacity" values="0.4;0.1;0.4" dur="2s" repeatCount="indefinite" />
        </circle>
      )}
      
      {/* Node background */}
      <circle
        cx={x}
        cy={y}
        r={size / 2}
        fill={`${color}20`}
        stroke={color}
        strokeWidth="3"
        strokeOpacity="0.6"
      />
      
      {/* Icon */}
      <foreignObject x={x - 18} y={y - 18} width={36} height={36}>
        <div className="w-full h-full flex items-center justify-center">
          <Icon className="w-8 h-8" style={{ color }} />
        </div>
      </foreignObject>
      
      {/* Label */}
      <text
        x={x}
        y={labelPosition === "above" ? y - size / 2 - 36 : y + size / 2 + 24}
        textAnchor="middle"
        className="text-base fill-muted-foreground font-medium"
      >
        {label}
      </text>
      
      {/* Value - larger font for readability */}
      <text
        x={x}
        y={labelPosition === "above" ? y - size / 2 - 12 : y + size / 2 + 48}
        textAnchor="middle"
        className="font-mono text-xl font-bold"
        fill={color}
      >
        {value} {unit}
      </text>
    </motion.g>
  );
};

const EnergyFlowDiagramComponent = ({
  solarPower,
  batteryPower,
  batteryLevel,
  consumption,
  gridPower,
  isGridExporting,
  showConnectionStatus = true,
  className,
}: EnergyFlowDiagramProps & { className?: string }) => {
  // Center position - increased vertical spacing
  const cx = 280;
  const cy = 240;
  
  // Node positions - more vertical spread to fill height
  const positions = {
    solar: { x: cx, y: 60 },
    center: { x: cx, y: cy },
    battery: { x: 80, y: 450 },
    home: { x: cx, y: 470 },
    grid: { x: 480, y: 450 },
  };

  // Curved paths - adjusted for new positions
  const paths = {
    solarToCenter: `M ${positions.solar.x} ${positions.solar.y + 40} Q ${cx} ${cy - 60} ${cx} ${cy - 28}`,
    centerToBattery: `M ${cx - 28} ${cy + 18} Q ${cx - 100} ${cy + 120} ${positions.battery.x + 40} ${positions.battery.y - 50}`,
    centerToHome: `M ${cx} ${cy + 28} Q ${cx} ${cy + 120} ${positions.home.x} ${positions.home.y - 50}`,
    centerToGrid: `M ${cx + 28} ${cy + 18} Q ${cx + 100} ${cy + 120} ${positions.grid.x - 40} ${positions.grid.y - 50}`,
  };

  const colors = {
    solar: "#F59E0B",
    battery: "#10B981",
    home: "#A855F7",
    grid: "#3B82F6",
    center: "#10B981",
  };

  return (
    <div className={`glass-card p-6 flex flex-col ${className || ''}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-foreground">Energy Flow</h3>
        <div className="flex items-center gap-3">
          {showConnectionStatus && (
            <ConnectionStatusIndicator showLabel={false} showReconnect={false} compact />
          )}
          <LiveIndicator />
        </div>
      </div>
      
      <div className="relative w-full max-w-[580px] mx-auto flex-1 flex items-center">
        <svg viewBox="0 0 560 560" className="w-full h-full" preserveAspectRatio="xMidYMid meet" style={{ overflow: "visible" }}>
          {/* Filters */}
          <defs>
            <filter id="particleGlow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="lineGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="centerGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="10" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Flow connections */}
          <FlowConnection
            pathId="path-solar"
            path={paths.solarToCenter}
            color={colors.solar}
            power={solarPower}
          />
          <FlowConnection
            pathId="path-battery"
            path={paths.centerToBattery}
            color={colors.battery}
            power={Math.abs(batteryPower)}
            reverse={batteryPower < 0}
          />
          <FlowConnection
            pathId="path-home"
            path={paths.centerToHome}
            color={colors.home}
            power={consumption}
          />
          <FlowConnection
            pathId="path-grid"
            path={paths.centerToGrid}
            color={colors.grid}
            power={Math.abs(gridPower)}
            reverse={!isGridExporting}
          />

          {/* Center hub */}
          <motion.g
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.15, duration: 0.4 }}
          >
            {/* Outer glow */}
            <circle
              cx={cx}
              cy={cy}
              r={30}
              fill="none"
              stroke={colors.center}
              strokeWidth="2"
              strokeOpacity="0.2"
              filter="url(#centerGlow)"
            >
              <animate attributeName="r" values="30;36;30" dur="3s" repeatCount="indefinite" />
            </circle>
            
            {/* Main circle */}
            <circle
              cx={cx}
              cy={cy}
              r={26}
              fill="hsl(var(--card))"
              stroke={colors.center}
              strokeWidth="2"
              strokeOpacity="0.6"
            />
            
            {/* Icon */}
            <foreignObject x={cx - 12} y={cy - 12} width={24} height={24}>
              <div className="w-full h-full flex items-center justify-center">
                <Zap className="w-5 h-5 text-primary" />
              </div>
            </foreignObject>
          </motion.g>

          {/* Energy nodes */}
          <EnergyNode
            icon={Sun}
            label="Solar"
            value={solarPower.toFixed(1)}
            unit="kW"
            color={colors.solar}
            position={positions.solar}
            isActive={solarPower > 0}
            delay={0}
            labelPosition="above"
          />
          
          {/* Battery with dynamic fill */}
          <BatteryNode
            level={batteryLevel}
            power={batteryPower}
            position={positions.battery}
            delay={0.05}
          />
          
          <EnergyNode
            icon={Home}
            label="Home"
            value={consumption.toFixed(1)}
            unit="kW"
            color={colors.home}
            position={positions.home}
            delay={0.1}
          />
          
          <EnergyNode
            icon={Grid3X3}
            label={isGridExporting ? "Exporting" : "Importing"}
            value={Math.abs(gridPower).toFixed(1)}
            unit="kW"
            color={colors.grid}
            position={positions.grid}
            isActive={!isGridExporting && gridPower !== 0}
            delay={0.15}
          />
        </svg>
      </div>
    </div>
  );
};

// Memoize to prevent unnecessary re-renders when parent state changes
export const EnergyFlowDiagram = memo(EnergyFlowDiagramComponent);