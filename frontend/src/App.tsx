import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/hooks/use-theme";
import { BillingConfigProvider } from "@/hooks/use-billing-config";
import { AuthProvider } from "@/hooks/use-auth";
import { UserModeProvider } from "@/hooks/use-user-mode";
import { SetupWizardProvider } from "@/hooks/use-setup-wizard";
import { TelemetryProvider } from "@/contexts/TelemetryContext";
import { TariffProvider } from "@/contexts/TariffContext";
import { UserRoleProvider } from "@/contexts/UserRoleContext";
import { DashboardLayoutProvider } from "@/contexts/DashboardLayoutContext";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import ProtectedRoute from "@/components/ProtectedRoute";
import Auth from "./pages/Auth";
import Index from "./pages/Index";
import Devices from "./pages/Devices";
import DeviceDetails from "./pages/DeviceDetails";
import DeviceSettings from "./pages/DeviceSettings";
import DeviceSettingsHybrid from "./pages/DeviceSettingsHybrid";
import DeviceManagement from "./pages/DeviceManagement";
import Telemetry from "./pages/Telemetry";
import SmartScheduler from "./pages/SmartScheduler";
import Settings from "./pages/Settings";
import Billing from "./pages/Billing";
import BillingSettings from "./pages/BillingSettings";
import TariffSettings from "./pages/TariffSettings";
import Notifications from "./pages/Notifications";
import Profile from "./pages/Profile";
import AlertCenter from "./pages/AlertCenter";
import Outages from "./pages/Outages";
import Savings from "./pages/Savings";
import UserManagement from "./pages/UserManagement";
import Commissioning from "./pages/Commissioning";
import Install from "./pages/Install";
import ClaimDevice from "./pages/ClaimDevice";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <ErrorBoundary variant="full">
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BillingConfigProvider>
          <AuthProvider>
            <UserModeProvider>
              <UserRoleProvider>
                <SetupWizardProvider>
                  <TelemetryProvider>
                    <TariffProvider>
                      <DashboardLayoutProvider>
                        <TooltipProvider>
                          {/* Skip to main content link for accessibility */}
                          <a href="#main-content" className="skip-link">
                            Skip to main content
                          </a>
                          <Toaster />
                          <Sonner />
                          <BrowserRouter>
                            <Routes>
                              <Route path="/auth" element={<Auth />} />
                              <Route path="/" element={<ProtectedRoute><Index /></ProtectedRoute>} />
                              <Route path="/devices" element={<ProtectedRoute><Devices /></ProtectedRoute>} />
                              <Route path="/devices/manage" element={<ProtectedRoute><DeviceManagement /></ProtectedRoute>} />
                              <Route path="/devices/:deviceId" element={<ProtectedRoute><DeviceDetails /></ProtectedRoute>} />
                              <Route path="/devices/:deviceId/settings" element={<ProtectedRoute><DeviceSettingsHybrid /></ProtectedRoute>} />
                              <Route path="/telemetry" element={<ProtectedRoute><Telemetry /></ProtectedRoute>} />
                              <Route path="/scheduler" element={<ProtectedRoute><SmartScheduler /></ProtectedRoute>} />
                              <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
                              <Route path="/settings/users" element={<ProtectedRoute><UserManagement /></ProtectedRoute>} />
                              <Route path="/billing" element={<ProtectedRoute><Billing /></ProtectedRoute>} />
                              <Route path="/billing/settings" element={<ProtectedRoute><BillingSettings /></ProtectedRoute>} />
                              <Route path="/settings/tariff" element={<ProtectedRoute><TariffSettings /></ProtectedRoute>} />
                              <Route path="/notifications" element={<ProtectedRoute><Notifications /></ProtectedRoute>} />
                              <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
                              <Route path="/alerts" element={<ProtectedRoute><AlertCenter /></ProtectedRoute>} />
                              <Route path="/outages" element={<ProtectedRoute><Outages /></ProtectedRoute>} />
                              <Route path="/savings" element={<ProtectedRoute><Savings /></ProtectedRoute>} />
                              <Route path="/commissioning" element={<ProtectedRoute><Commissioning /></ProtectedRoute>} />
                              <Route path="/devices/claim" element={<ProtectedRoute><ClaimDevice /></ProtectedRoute>} />
                              <Route path="/install" element={<Install />} />
                              <Route path="*" element={<NotFound />} />
                            </Routes>
                          </BrowserRouter>
                        </TooltipProvider>
                      </DashboardLayoutProvider>
                    </TariffProvider>
                  </TelemetryProvider>
                </SetupWizardProvider>
              </UserRoleProvider>
            </UserModeProvider>
          </AuthProvider>
        </BillingConfigProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </ErrorBoundary>
);

export default App;
