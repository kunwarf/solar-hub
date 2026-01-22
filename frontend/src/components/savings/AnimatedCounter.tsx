import { useEffect, useState, useRef } from 'react';
import { motion, useSpring, useTransform } from 'framer-motion';

interface AnimatedCounterProps {
  value: number;
  duration?: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  className?: string;
}

export function AnimatedCounter({ 
  value, 
  duration = 2, 
  prefix = '', 
  suffix = '',
  decimals = 0,
  className = ''
}: AnimatedCounterProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const prevValueRef = useRef(0);
  
  const spring = useSpring(0, { 
    stiffness: 50, 
    damping: 20,
    duration: duration * 1000 
  });
  
  const display = useTransform(spring, (latest) => {
    return Math.round(latest);
  });

  useEffect(() => {
    spring.set(value);
    
    const unsubscribe = display.on('change', (latest) => {
      setDisplayValue(latest);
    });
    
    prevValueRef.current = value;
    
    return () => unsubscribe();
  }, [value, spring, display]);

  const formatNumber = (num: number) => {
    if (decimals > 0) {
      return num.toLocaleString('en-PK', { 
        minimumFractionDigits: decimals, 
        maximumFractionDigits: decimals 
      });
    }
    return num.toLocaleString('en-PK');
  };

  return (
    <motion.span 
      className={className}
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
    >
      {prefix}{formatNumber(displayValue)}{suffix}
    </motion.span>
  );
}
