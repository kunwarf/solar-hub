import * as React from "react";
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
import { AdminAuthProvider } from "@/contexts/AdminAuthContext";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import ProtectedRoute from "@/components/ProtectedRoute";
import { AdminGuard } from "@/components/admin/AdminGuard";
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
import AdminLogin from "./pages/admin/AdminLogin";
import AdminDashboard from "./pages/admin/Index";
import AuditLog from "./pages/admin/AuditLog";
import ElectricityProviders from "./pages/admin/ElectricityProviders";
import TariffManagement from "./pages/admin/TariffManagement";
import FirmwareVersions from "./pages/admin/FirmwareVersions";
import OTACampaigns from "./pages/admin/OTACampaigns";
import SystemSettings from "./pages/admin/SystemSettings";
import AdminUsers from "./pages/admin/AdminUsers";
import LoadSheddingSchedules from "./pages/admin/LoadSheddingSchedules";
import AIPrompts from "./pages/admin/AIPrompts";

const queryClient = new QueryClient();

const App = () => (
  <ErrorBoundary variant="full">
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BillingConfigProvider>
          <AuthProvider>
            <UserModeProvider>
              <UserRoleProvider>
                <AdminAuthProvider>
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

                              {/* Admin Routes */}
                              <Route path="/admin/login" element={<AdminLogin />} />
                              <Route path="/admin" element={<AdminGuard><AdminDashboard /></AdminGuard>} />
                              <Route path="/admin/audit-log" element={<AdminGuard requiredPermission="view_audit_log"><AuditLog /></AdminGuard>} />
                              <Route path="/admin/providers" element={<AdminGuard requiredPermission="manage_providers"><ElectricityProviders /></AdminGuard>} />
                              <Route path="/admin/tariffs" element={<AdminGuard requiredPermission="manage_tariffs"><TariffManagement /></AdminGuard>} />
                              <Route path="/admin/load-shedding" element={<AdminGuard requiredPermission="manage_load_shedding"><LoadSheddingSchedules /></AdminGuard>} />
                              <Route path="/admin/users" element={<AdminGuard requiredPermission="manage_users"><AdminUsers /></AdminGuard>} />
                              <Route path="/admin/ai-prompts" element={<AdminGuard><AIPrompts /></AdminGuard>} />
                              <Route path="/admin/firmware-versions" element={<AdminGuard requiredPermission="manage_firmware"><FirmwareVersions /></AdminGuard>} />
                              <Route path="/admin/ota-campaigns" element={<AdminGuard requiredPermission="manage_campaigns"><OTACampaigns /></AdminGuard>} />
                              <Route path="/admin/system-settings" element={<AdminGuard><SystemSettings /></AdminGuard>} />

                              <Route path="*" element={<NotFound />} />
                            </Routes>
                          </BrowserRouter>
                          </TooltipProvider>
                        </DashboardLayoutProvider>
                      </TariffProvider>
                    </TelemetryProvider>
                  </SetupWizardProvider>
                </AdminAuthProvider>
              </UserRoleProvider>
            </UserModeProvider>
          </AuthProvider>
        </BillingConfigProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </ErrorBoundary>
);

export default App;
