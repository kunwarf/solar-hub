import { motion } from "framer-motion";
import { Cloud, Sun, CloudRain, CloudSnow, Wind, Droplets, Thermometer } from "lucide-react";
import { cn } from "@/lib/utils";

interface WeatherData {
  temperature: number;
  condition: "sunny" | "cloudy" | "rainy" | "snowy" | "windy";
  humidity: number;
  windSpeed: number;
  solarForecast: number; // percentage of expected solar production
  sunrise: string;
  sunset: string;
}

const mockWeather: WeatherData = {
  temperature: 24,
  condition: "sunny",
  humidity: 45,
  windSpeed: 12,
  solarForecast: 92,
  sunrise: "06:15",
  sunset: "18:42",
};

const conditionIcons = {
  sunny: Sun,
  cloudy: Cloud,
  rainy: CloudRain,
  snowy: CloudSnow,
  windy: Wind,
};

const conditionColors = {
  sunny: "text-solar",
  cloudy: "text-muted-foreground",
  rainy: "text-info",
  snowy: "text-info",
  windy: "text-accent",
};

interface WeatherWidgetProps {
  className?: string;
}

export function WeatherWidget({ className }: WeatherWidgetProps) {
  const weather = mockWeather;
  const ConditionIcon = conditionIcons[weather.condition];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("glass-card p-4", className)}
    >
      <div className="flex items-start justify-between gap-4">
        {/* Left: Temperature and condition */}
        <div className="flex items-center gap-3">
          <div className={cn(
            "w-12 h-12 rounded-xl flex items-center justify-center",
            weather.condition === "sunny" ? "bg-solar/20" : "bg-secondary"
          )}>
            <ConditionIcon className={cn("w-6 h-6", conditionColors[weather.condition])} />
          </div>
          <div>
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-bold text-foreground">{weather.temperature}</span>
              <span className="text-muted-foreground">°C</span>
            </div>
            <span className="text-sm text-muted-foreground capitalize">{weather.condition}</span>
          </div>
        </div>

        {/* Right: Solar forecast */}
        <div className="text-right">
          <div className="flex items-center gap-1.5 justify-end mb-1">
            <Sun className="w-4 h-4 text-solar" />
            <span className="text-sm font-medium text-foreground">Solar Forecast</span>
          </div>
          <div className="flex items-baseline gap-1 justify-end">
            <span className={cn(
              "text-xl font-bold",
              weather.solarForecast >= 80 ? "text-success" : 
              weather.solarForecast >= 50 ? "text-warning" : "text-muted-foreground"
            )}>
              {weather.solarForecast}%
            </span>
          </div>
          <span className="text-xs text-muted-foreground">of expected</span>
        </div>
      </div>

      {/* Bottom: Additional metrics */}
      <div className="grid grid-cols-4 gap-2 mt-4 pt-3 border-t border-border/50">
        <div className="flex flex-col items-center">
          <Droplets className="w-4 h-4 text-info mb-1" />
          <span className="text-xs font-mono text-foreground">{weather.humidity}%</span>
          <span className="text-[10px] text-muted-foreground">Humidity</span>
        </div>
        <div className="flex flex-col items-center">
          <Wind className="w-4 h-4 text-accent mb-1" />
          <span className="text-xs font-mono text-foreground">{weather.windSpeed}</span>
          <span className="text-[10px] text-muted-foreground">km/h</span>
        </div>
        <div className="flex flex-col items-center">
          <Sun className="w-4 h-4 text-solar mb-1" />
          <span className="text-xs font-mono text-foreground">{weather.sunrise}</span>
          <span className="text-[10px] text-muted-foreground">Sunrise</span>
        </div>
        <div className="flex flex-col items-center">
          <Sun className="w-4 h-4 text-warning mb-1" />
          <span className="text-xs font-mono text-foreground">{weather.sunset}</span>
          <span className="text-[10px] text-muted-foreground">Sunset</span>
        </div>
      </div>
    </motion.div>
  );
}
