import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Cloud, Sun, CloudRain, CloudSnow, Wind, Droplets, Thermometer } from "lucide-react";
import { cn } from "@/lib/utils";
import dashboardService from "@/api/services/dashboard.service";

interface WeatherDisplayData {
  temperature: number;
  condition: "sunny" | "cloudy" | "rainy" | "snowy" | "windy";
  humidity: number;
  windSpeed: number;
  solarForecast: number;
  sunrise: string;
  sunset: string;
}

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

const validConditions = ["sunny", "cloudy", "rainy", "snowy", "windy"] as const;
type Condition = typeof validConditions[number];

function toCondition(s: string): Condition {
  return validConditions.includes(s as Condition) ? (s as Condition) : "sunny";
}

interface WeatherWidgetProps {
  className?: string;
}

export function WeatherWidget({ className }: WeatherWidgetProps) {
  const [weather, setWeather] = useState<WeatherDisplayData>({
    temperature: 0, condition: "sunny", humidity: 0, windSpeed: 0,
    solarForecast: 0, sunrise: "06:00", sunset: "18:00",
  });

  const fetchData = useCallback(async () => {
    try {
      const data = await dashboardService.getWeather();
      setWeather({
        temperature: data.temperature,
        condition: toCondition(data.condition),
        humidity: data.humidity,
        windSpeed: data.wind_speed,
        solarForecast: data.solar_forecast,
        sunrise: data.sunrise,
        sunset: data.sunset,
      });
    } catch {
      // Keep existing data on error
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 1800000); // 30 minutes
    return () => clearInterval(interval);
  }, [fetchData]);

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
