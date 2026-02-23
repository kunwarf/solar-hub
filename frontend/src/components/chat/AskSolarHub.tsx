import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  MessageCircle, 
  X, 
  Send, 
  Sparkles, 
  Clock, 
  TrendingUp, 
  Battery, 
  Sun, 
  Zap,
  Calendar,
  ArrowRight,
  ThumbsUp,
  ThumbsDown,
  RotateCcw
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { useNavigate } from 'react-router-dom';
import { energyStats } from '@/data/mockData';

// Types for chat interface - structured for AI integration
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  data?: {
    value?: string | number;
    unit?: string;
    trend?: { value: number; isPositive: boolean };
    chart?: 'mini-bar' | 'mini-line' | 'progress';
    chartData?: number[];
    link?: { label: string; url: string };
  };
}

export interface QueryIntent {
  type: 'generation' | 'savings' | 'outage' | 'battery' | 'comparison' | 'performance' | 'unknown';
  timeframe?: 'today' | 'week' | 'month' | 'year' | 'last_outage';
  entities?: string[];
}

// Keyword patterns for intent detection
const intentPatterns: { type: QueryIntent['type']; patterns: RegExp[] }[] = [
  {
    type: 'generation',
    patterns: [
      /generat(e|ed|ion)/i,
      /produc(e|ed|tion)/i,
      /solar.*power/i,
      /how much.*solar/i,
      /kWh.*(today|week|month)/i,
    ],
  },
  {
    type: 'savings',
    patterns: [
      /sav(e|ed|ings)/i,
      /money/i,
      /cost/i,
      /bill/i,
      /Rs\.?/i,
      /rupees?/i,
    ],
  },
  {
    type: 'outage',
    patterns: [
      /outage/i,
      /power.?cut/i,
      /blackout/i,
      /load.?shed/i,
      /grid.*(down|off)/i,
    ],
  },
  {
    type: 'battery',
    patterns: [
      /battery/i,
      /charge/i,
      /soc/i,
      /state.?of.?charge/i,
      /backup/i,
      /health/i,
    ],
  },
  {
    type: 'comparison',
    patterns: [
      /compar/i,
      /vs\.?/i,
      /versus/i,
      /difference/i,
      /this.*last/i,
      /better|worse/i,
    ],
  },
  {
    type: 'performance',
    patterns: [
      /best/i,
      /peak/i,
      /record/i,
      /highest/i,
      /maximum/i,
      /top/i,
      /perform/i,
    ],
  },
];

const timeframePatterns: { timeframe: QueryIntent['timeframe']; patterns: RegExp[] }[] = [
  { timeframe: 'today', patterns: [/today/i, /now/i, /current/i] },
  { timeframe: 'week', patterns: [/week/i, /7 days/i] },
  { timeframe: 'month', patterns: [/month/i, /30 days/i] },
  { timeframe: 'year', patterns: [/year/i, /annual/i, /12 months/i] },
  { timeframe: 'last_outage', patterns: [/last.*outage/i, /recent.*outage/i] },
];

// Detect intent from user query
function detectIntent(query: string): QueryIntent {
  let detectedType: QueryIntent['type'] = 'unknown';
  let detectedTimeframe: QueryIntent['timeframe'] = 'today';

  // Detect intent type
  for (const { type, patterns } of intentPatterns) {
    if (patterns.some(p => p.test(query))) {
      detectedType = type;
      break;
    }
  }

  // Detect timeframe
  for (const { timeframe, patterns } of timeframePatterns) {
    if (patterns.some(p => p.test(query))) {
      detectedTimeframe = timeframe;
      break;
    }
  }

  return { type: detectedType, timeframe: detectedTimeframe };
}

// Generate response based on intent
function generateResponse(intent: QueryIntent): ChatMessage['data'] & { content: string } {
  switch (intent.type) {
    case 'generation': {
      const value = intent.timeframe === 'today' ? energyStats.dailyProduction :
                    intent.timeframe === 'week' ? 156 :
                    intent.timeframe === 'month' ? 680 : 8200;
      const timeLabel = intent.timeframe === 'today' ? 'today' :
                       intent.timeframe === 'week' ? 'this week' :
                       intent.timeframe === 'month' ? 'this month' : 'this year';
      return {
        content: `You generated **${value} kWh** ${timeLabel}. That's ${intent.timeframe === 'today' ? '10% above' : '8% above'} your average! 🎉`,
        value,
        unit: 'kWh',
        trend: { value: intent.timeframe === 'today' ? 10 : 8, isPositive: true },
        chart: 'mini-bar',
        chartData: [32, 38, 42, 35, 45, 40, value],
        link: { label: 'View detailed production', url: '/telemetry' },
      };
    }

    case 'savings': {
      const dailySavings = Math.round(energyStats.dailyProduction * 12.2);
      const value = intent.timeframe === 'today' ? dailySavings :
                    intent.timeframe === 'week' ? 3200 :
                    intent.timeframe === 'month' ? 14500 : 165000;
      const timeLabel = intent.timeframe === 'today' ? 'today' :
                       intent.timeframe === 'week' ? 'this week' :
                       intent.timeframe === 'month' ? 'this month' : 'this year';
      return {
        content: `Your savings ${timeLabel} are **Rs. ${value.toLocaleString()}**. You're on track to save Rs. ${Math.round(value * (intent.timeframe === 'today' ? 30 : 1.1)).toLocaleString()} by end of ${intent.timeframe === 'today' ? 'month' : 'next period'}!`,
        value,
        unit: 'Rs.',
        trend: { value: 15, isPositive: true },
        link: { label: 'View savings breakdown', url: '/savings' },
      };
    }

    case 'outage': {
      return {
        content: `Your last outage was **2 days ago** on January 20th at 3:15 PM. It lasted 45 minutes. Your battery kept essential loads running throughout! ⚡`,
        value: '2 days ago',
        link: { label: 'View outage history', url: '/outages' },
      };
    }

    case 'battery': {
      const soc = energyStats.batteryLevel;
      const healthStatus = soc > 60 ? 'excellent' : soc > 40 ? 'good' : 'needs attention';
      return {
        content: `Your battery is at **${soc}%** charge and in **${healthStatus}** health. ${soc > 60 ? 'You have about 5 hours of backup available.' : 'Consider charging during peak solar hours.'}`,
        value: soc,
        unit: '%',
        chart: 'progress',
        link: { label: 'View battery details', url: '/telemetry?device=bat-001' },
      };
    }

    case 'comparison': {
      return {
        content: `**This week vs last week:**\n• Generation: 156 kWh vs 140 kWh (+11.4%)\n• Savings: Rs. 3,200 vs Rs. 2,900 (+10.3%)\n• Self-sufficiency: 78% vs 72% (+6%)`,
        chart: 'mini-bar',
        chartData: [140, 156],
        link: { label: 'View comparison charts', url: '/' },
      };
    }

    case 'performance': {
      return {
        content: `Your **best performing day** this month was January 15th with **52.3 kWh** generated! That's 22% above your daily average. It was a clear sunny day with peak output at 1:30 PM. 🌟`,
        value: 52.3,
        unit: 'kWh',
        trend: { value: 22, isPositive: true },
        link: { label: 'View performance analytics', url: '/savings' },
      };
    }

    default:
      return {
        content: `I'm not sure I understand that query. Try asking me about:\n• Your daily/weekly/monthly generation\n• Energy savings and costs\n• Battery status and health\n• Outage history\n• Performance comparisons`,
      };
  }
}

// Suggested queries
const suggestedQueries = [
  { text: "How much did I generate today?", icon: Sun },
  { text: "What are my savings this month?", icon: TrendingUp },
  { text: "Is my battery healthy?", icon: Battery },
  { text: "Compare this week to last week", icon: Calendar },
];

// Mini chart component
const MiniChart = ({ type, data }: { type: 'mini-bar' | 'mini-line' | 'progress'; data?: number[] }) => {
  if (type === 'progress' && data?.[0]) {
    return (
      <div className="w-full h-2 bg-muted rounded-full overflow-hidden mt-2">
        <div 
          className="h-full bg-primary rounded-full transition-all"
          style={{ width: `${data[0]}%` }}
        />
      </div>
    );
  }

  if (type === 'mini-bar' && data) {
    const max = Math.max(...data);
    return (
      <div className="flex items-end gap-1 h-8 mt-2">
        {data.map((val, i) => (
          <div
            key={i}
            className={cn(
              "flex-1 rounded-sm transition-all",
              i === data.length - 1 ? "bg-primary" : "bg-primary/30"
            )}
            style={{ height: `${(val / max) * 100}%` }}
          />
        ))}
      </div>
    );
  }

  return null;
};

export const AskSolarHub = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim()) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    // Haptic feedback
    if ('vibrate' in navigator) {
      navigator.vibrate(10);
    }

    // Simulate processing delay
    await new Promise(resolve => setTimeout(resolve, 800 + Math.random() * 400));

    // Detect intent and generate response
    const intent = detectIntent(text.trim());
    const response = generateResponse(intent);

    const assistantMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: response.content,
      timestamp: new Date(),
      data: {
        value: response.value,
        unit: response.unit,
        trend: response.trend,
        chart: response.chart,
        chartData: response.chartData,
        link: response.link,
      },
    };

    setMessages(prev => [...prev, assistantMessage]);
    setIsTyping(false);
  }, []);

  const handleSend = useCallback(() => {
    sendMessage(input);
  }, [input, sendMessage]);

  const handleSuggestion = (query: string) => {
    sendMessage(query);
  };

  const handleLinkClick = (url: string) => {
    setIsOpen(false);
    navigate(url);
  };

  const clearHistory = () => {
    setMessages([]);
  };

  return (
    <>
      {/* Floating Button */}
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setIsOpen(true)}
            className="fixed bottom-24 right-4 md:bottom-6 md:right-6 z-50 w-14 h-14 rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/25 flex items-center justify-center"
          >
            <MessageCircle className="w-6 h-6" />
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-accent rounded-full flex items-center justify-center">
              <Sparkles className="w-2.5 h-2.5 text-accent-foreground" />
            </span>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Chat Drawer */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsOpen(false)}
              className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50"
            />

            {/* Drawer */}
            <motion.div
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              className="fixed bottom-0 left-0 right-0 z-50 bg-card border-t rounded-t-2xl shadow-2xl max-h-[85vh] flex flex-col md:right-4 md:left-auto md:bottom-4 md:w-[420px] md:rounded-2xl md:border"
            >
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                    <Sparkles className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold">Ask Solar Hub</h3>
                    <p className="text-xs text-muted-foreground">AI-powered insights</p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {messages.length > 0 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={clearHistory}
                      className="h-8 w-8"
                    >
                      <RotateCcw className="w-4 h-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setIsOpen(false)}
                    className="h-8 w-8"
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {/* Messages */}
              <ScrollArea className="flex-1 p-4" ref={scrollRef}>
                <div className="space-y-4">
                  {messages.length === 0 ? (
                    <div className="space-y-4">
                      <p className="text-sm text-muted-foreground text-center py-4">
                        Ask me anything about your solar system!
                      </p>
                      
                      {/* Suggested queries */}
                      <div className="space-y-2">
                        <p className="text-xs text-muted-foreground font-medium">Try asking:</p>
                        {suggestedQueries.map((query, i) => (
                          <button
                            key={i}
                            onClick={() => handleSuggestion(query.text)}
                            className="w-full flex items-center gap-3 p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors text-left text-sm"
                          >
                            <query.icon className="w-4 h-4 text-primary shrink-0" />
                            <span>{query.text}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    messages.map((msg) => (
                      <div
                        key={msg.id}
                        className={cn(
                          "flex gap-3",
                          msg.role === 'user' ? 'justify-end' : 'justify-start'
                        )}
                      >
                        {msg.role === 'assistant' && (
                          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                            <Sparkles className="w-4 h-4 text-primary" />
                          </div>
                        )}
                        
                        <div
                          className={cn(
                            "max-w-[80%] rounded-2xl p-3",
                            msg.role === 'user'
                              ? 'bg-primary text-primary-foreground rounded-br-md'
                              : 'bg-muted rounded-bl-md'
                          )}
                        >
                          <p className="text-sm whitespace-pre-wrap">
                            {msg.content.split(/(\*\*[^*]+\*\*)/).map((part, i) => {
                              if (part.startsWith('**') && part.endsWith('**')) {
                                return <strong key={i}>{part.slice(2, -2)}</strong>;
                              }
                              return part;
                            })}
                          </p>

                          {/* Chart */}
                          {msg.data?.chart && msg.data.chartData && (
                            <MiniChart 
                              type={msg.data.chart} 
                              data={msg.data.chart === 'progress' ? [msg.data.value as number] : msg.data.chartData} 
                            />
                          )}

                          {/* Trend */}
                          {msg.data?.trend && (
                            <div className={cn(
                              "flex items-center gap-1 text-xs mt-2",
                              msg.data.trend.isPositive ? "text-success" : "text-destructive"
                            )}>
                              <TrendingUp className={cn(
                                "w-3 h-3",
                                !msg.data.trend.isPositive && "rotate-180"
                              )} />
                              {msg.data.trend.isPositive ? '+' : '-'}{Math.abs(msg.data.trend.value)}% vs average
                            </div>
                          )}

                          {/* Link */}
                          {msg.data?.link && (
                            <button
                              onClick={() => handleLinkClick(msg.data!.link!.url)}
                              className="flex items-center gap-1 text-xs text-primary mt-2 hover:underline"
                            >
                              {msg.data.link.label}
                              <ArrowRight className="w-3 h-3" />
                            </button>
                          )}
                        </div>

                        {msg.role === 'user' && (
                          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shrink-0">
                            <span className="text-xs font-medium text-primary-foreground">You</span>
                          </div>
                        )}
                      </div>
                    ))
                  )}

                  {/* Typing indicator */}
                  {isTyping && (
                    <div className="flex gap-3">
                      <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                        <Sparkles className="w-4 h-4 text-primary" />
                      </div>
                      <div className="bg-muted rounded-2xl rounded-bl-md p-3">
                        <div className="flex gap-1">
                          <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                          <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                          <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </ScrollArea>

              {/* Input */}
              <div className="p-4 border-t">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSend();
                  }}
                  className="flex gap-2"
                >
                  <Input
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask anything about your solar system..."
                    className="flex-1"
                    disabled={isTyping}
                  />
                  <Button 
                    type="submit" 
                    size="icon"
                    disabled={!input.trim() || isTyping}
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </form>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
};

export default AskSolarHub;
