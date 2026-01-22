import { useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Home, ArrowLeft, Search, HelpCircle } from "lucide-react";

const NotFound = () => {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="text-center max-w-md">
        {/* Animated illustration */}
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 200, damping: 20 }}
          className="mb-8"
        >
          <svg viewBox="0 0 200 160" className="w-48 h-40 mx-auto">
            {/* Sun with rays */}
            <motion.g
              animate={{ rotate: 360 }}
              transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
              style={{ transformOrigin: "100px 50px" }}
            >
              <circle cx="100" cy="50" r="25" className="fill-solar/20" />
              {[0, 45, 90, 135, 180, 225, 270, 315].map((angle, i) => (
                <motion.line
                  key={i}
                  x1="100"
                  y1="50"
                  x2={100 + Math.cos((angle * Math.PI) / 180) * 40}
                  y2={50 + Math.sin((angle * Math.PI) / 180) * 40}
                  className="stroke-solar/30"
                  strokeWidth="2"
                  strokeLinecap="round"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 2, delay: i * 0.2, repeat: Infinity }}
                />
              ))}
            </motion.g>
            <circle cx="100" cy="50" r="18" className="fill-solar" />
            
            {/* Solar panel - disconnected */}
            <motion.g
              initial={{ y: 10 }}
              animate={{ y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <rect x="50" y="100" width="100" height="50" rx="4" className="fill-card stroke-border" strokeWidth="2" />
              <line x1="75" y1="100" x2="75" y2="150" className="stroke-border" strokeWidth="1" />
              <line x1="100" y1="100" x2="100" y2="150" className="stroke-border" strokeWidth="1" />
              <line x1="125" y1="100" x2="125" y2="150" className="stroke-border" strokeWidth="1" />
              <line x1="50" y1="125" x2="150" y2="125" className="stroke-border" strokeWidth="1" />
            </motion.g>
            
            {/* Broken connection indicator */}
            <motion.path
              d="M100 75 L100 95"
              className="stroke-destructive"
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray="5 5"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.5, delay: 0.4 }}
            />
            
            {/* X mark */}
            <motion.g
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.6, type: "spring" }}
            >
              <circle cx="170" cy="85" r="15" className="fill-destructive/20" />
              <line x1="163" y1="78" x2="177" y2="92" className="stroke-destructive" strokeWidth="3" strokeLinecap="round" />
              <line x1="177" y1="78" x2="163" y2="92" className="stroke-destructive" strokeWidth="3" strokeLinecap="round" />
            </motion.g>
          </svg>
        </motion.div>

        {/* 404 Text */}
        <motion.h1
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="text-6xl font-bold text-foreground mb-2"
        >
          404
        </motion.h1>

        <motion.h2
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="text-xl font-semibold text-foreground mb-3"
        >
          Page Not Found
        </motion.h2>

        <motion.p
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="text-muted-foreground mb-8"
        >
          The page you're looking for doesn't exist or has been moved. 
          Let's get you back on track.
        </motion.p>

        {/* Action buttons */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="flex flex-col sm:flex-row gap-3 justify-center"
        >
          <Button onClick={() => navigate("/")} className="gap-2">
            <Home className="w-4 h-4" />
            Go to Dashboard
          </Button>
          <Button variant="outline" onClick={() => navigate(-1)} className="gap-2">
            <ArrowLeft className="w-4 h-4" />
            Go Back
          </Button>
        </motion.div>

        {/* Helpful links */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
          className="mt-8 pt-6 border-t border-border"
        >
          <p className="text-sm text-muted-foreground mb-3">Looking for something specific?</p>
          <div className="flex flex-wrap gap-2 justify-center">
            <Button variant="ghost" size="sm" onClick={() => navigate("/devices")} className="text-xs">
              Devices
            </Button>
            <Button variant="ghost" size="sm" onClick={() => navigate("/billing")} className="text-xs">
              Billing
            </Button>
            <Button variant="ghost" size="sm" onClick={() => navigate("/settings")} className="text-xs">
              Settings
            </Button>
            <Button variant="ghost" size="sm" onClick={() => navigate("/alerts")} className="text-xs">
              Alerts
            </Button>
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default NotFound;
