# Lovable Prompts for Solar Hub Frontend

**Document Version:** 1.0
**Date:** January 2026
**Purpose:** Comprehensive prompts to finalize the Solar Hub frontend using Lovable AI

---

## Table of Contents

1. [Current Prototype Analysis](#current-prototype-analysis)
2. [MVP Prompts](#mvp-prompts)
   - [1. Guided Setup Wizard](#1-guided-setup-wizard)
   - [2. Real-Time WebSocket Integration](#2-real-time-websocket-integration)
   - [3. Pakistani DISCO Tariff System](#3-pakistani-disco-tariff-system)
   - [4. Enhanced Load Shedding Tracking](#4-enhanced-load-shedding-tracking)
   - [5. What-If Scenario Calculator](#5-what-if-scenario-calculator)
   - [6. ROI Calculator & Savings Dashboard](#6-roi-calculator--savings-dashboard)
   - [7. Notification Configuration System](#7-notification-configuration-system)
   - [8. User Management & Access Control](#8-user-management--access-control)
   - [9. Device Commissioning Flow](#9-device-commissioning-flow)
   - [10. Enhanced Dashboard Customization](#10-enhanced-dashboard-customization)
   - [11. PWA & Offline Support](#11-pwa--offline-support)
   - [12. AI Insights Panel](#12-ai-insights-panel)
   - [13. Mobile-Optimized Improvements](#13-mobile-optimized-improvements)
3. [Phase 2+ Prompts](#phase-2-prompts)
4. [Implementation Priority](#implementation-priority)

---

## Current Prototype Analysis

### Already Implemented (Good Foundation)

| Feature | Status | Notes |
|---------|--------|-------|
| Tech Stack | ✅ Complete | React + TypeScript + Vite + Tailwind + shadcn/ui |
| Dashboard Page | ✅ Complete | Stats, charts, widgets |
| Energy Flow Diagram | ✅ Complete | Animated with particle effects |
| Load Shedding Widget | ✅ Basic | Needs full page with history |
| Billing Page | ✅ Basic | Needs Pakistani tariff system |
| Telemetry Page | ✅ Complete | Device-specific views |
| Settings Page | ✅ Basic | Needs more configuration options |
| Authentication | ✅ Mock | Context-based, needs real integration |
| Simple/Advanced Mode | ✅ Complete | Toggle in user settings |
| Theme Support | ✅ Complete | Dark/Light modes |
| Responsive Design | ✅ Complete | Mobile-first approach |

### Gaps to Fill for MVP

- Guided Setup Wizard for new users
- Pakistani DISCO tariff calculations
- Real-time WebSocket data
- Full outage tracking page
- What-If scenario calculator
- Notification configuration
- User/Role management
- Device commissioning workflow
- PWA offline support

---

## MVP Prompts

### 1. Guided Setup Wizard

**Priority:** Critical
**Estimated Complexity:** Medium

```
Create a step-by-step guided setup wizard for first-time users. The wizard should appear automatically for new accounts and include these steps:

Step 1 - Welcome: Show a brief intro with value proposition. Include a "Skip for now" option for experienced users.

Step 2 - Profile Setup: Collect user's name, location (city selection dropdown with major Pakistani cities: Lahore, Karachi, Islamabad, Multan, Peshawar, Faisalabad), and contact preferences.

Step 3 - Add First Device: Show two options - QR code scan (with camera access) or manual activation code entry. Include a visual guide showing where to find the code on the device.

Step 4 - Connection Test: Animated progress showing device connection verification with clear success/failure states.

Step 5 - Tariff Selection: Pre-populated dropdown with Pakistani DISCO tariffs (LESCO, K-Electric, MEPCO, IESCO, PESCO, FESCO, HESCO, QESCO, GEPCO, SEPCO). Show basic rate info for selected DISCO.

Step 6 - Set a Goal: Let user set a monthly savings goal in PKR with a slider (Rs. 1,000 - Rs. 50,000).

Step 7 - Dashboard Tour: Brief overlay highlighting key dashboard features (power flow, savings, alerts).

Use a progress stepper at the top. Save progress so users can resume if interrupted. Add a "Skip tour" option but make it subtle.
```

---

### 2. Real-Time WebSocket Integration

**Priority:** High
**Estimated Complexity:** Medium

```
Add WebSocket integration for real-time telemetry updates. Create a useWebSocket hook that:

1. Connects to the telemetry WebSocket endpoint
2. Handles reconnection with exponential backoff (5s, 10s, 20s, max 60s)
3. Shows connection status indicator (green dot when connected, yellow when reconnecting, red when failed)
4. Pushes updates to a global telemetry context

Update the EnergyFlowDiagram to consume real-time data instead of mock data. Add a "Live" indicator that pulses when receiving data.

For now, create mock WebSocket simulation that generates realistic solar data based on time of day:
- Solar power: 0 at night, ramps up 6am-12pm, peaks at noon, ramps down 12pm-6pm
- Battery: charges when solar > consumption, discharges at night
- Grid: imports when solar + battery insufficient

Add a reconnect button in the connection status area.
```

---

### 3. Pakistani DISCO Tariff System

**Priority:** Critical
**Estimated Complexity:** High

```
Implement a comprehensive Pakistani electricity tariff system:

1. Create a tariff configuration page (Settings > Tariff Settings) with:
   - DISCO provider selection dropdown with all 10 DISCOs
   - Consumer category: Residential (with protected/unprotected subcategory), Commercial, Industrial, Agricultural
   - Connection type: Single Phase, Three Phase
   - Sanctioned Load input (kW)
   - Net metering enabled toggle

2. Implement slab-based billing calculation. For Residential Protected:
   - 1-100 units: Rs. 7.74/kWh
   - 101-200 units: Rs. 10.06/kWh
   - 201-300 units: Rs. 14.82/kWh
   - 301-700 units: Rs. 24.40/kWh
   - 700+ units: Rs. 30.72/kWh

3. Add these charges to bill calculation:
   - Fixed charges (based on connection type)
   - Fuel Price Adjustment (FPA) - make this editable monthly
   - Quarterly Tariff Adjustment (QTA)
   - Electricity Duty (1.5%)
   - GST (17% on amount > Rs. 25,000)
   - TV Fee (Rs. 35 flat)
   - Net metering export rate (Rs. 19.32/kWh for NEPRA approved)

4. Create a visual bill breakdown showing each component as a stacked bar chart. Currency should always be PKR (Rs.).
```

---

### 4. Enhanced Load Shedding Tracking

**Priority:** Critical
**Estimated Complexity:** Medium

```
Expand the LoadSheddingTracker component to a full-featured outage management system:

1. Create a dedicated Outages page (/outages) with:
   - Current grid status (large indicator)
   - Today's outage summary (count, total duration)
   - Outage timeline for today (horizontal bar showing outage periods)
   - This week's outage calendar (mini calendar with outage indicators)

2. Add outage history table with columns:
   - Date, Start Time, End Time, Duration
   - Type (Scheduled/Unscheduled/Unknown)
   - Battery usage during outage (kWh)
   - Backup status (Full backup / Partial backup / No backup)

3. Create monthly outage statistics cards:
   - Total outages this month
   - Average outage duration
   - Longest outage
   - Total backup time provided
   - "Hours of darkness avoided" (with happy sun icon)

4. Add outage alerts section:
   - Notification when grid goes down
   - Low battery warning during outage
   - Prediction: "Battery will last X more hours at current load"

5. Add export button to download outage report as PDF or CSV.

Use mock data with realistic Pakistani load shedding patterns (typically 2-4 hours, more frequent in summer).
```

---

### 5. What-If Scenario Calculator

**Priority:** High
**Estimated Complexity:** Medium

```
Create a What-If Scenario calculator on the Billing page (add as a tab or expandable section):

Scenarios to implement:

1. "Add More Panels" scenario:
   - Input: Additional capacity in kW (slider: 1-20 kW)
   - Output: Show estimated additional generation, new bill estimate, additional savings, updated ROI timeline

2. "Add Battery Storage" scenario:
   - Input: Battery capacity in kWh (slider: 5-50 kWh)
   - Output: Show backup hours gained, self-consumption increase, bill reduction, payback period

3. "Change Tariff Plan" scenario:
   - Dropdown to select different DISCO or category
   - Show side-by-side comparison of current vs new plan
   - Highlight savings or additional cost

4. "Increase Load" scenario:
   - Input: Additional monthly consumption (slider: 0-500 kWh)
   - Output: Impact on grid import, bill increase, self-sufficiency change

For each scenario, show:
- Before/After comparison table
- Monthly savings impact
- Annual savings projection
- Visual chart comparing scenarios

Add a "Save Scenario" button to track favorite comparisons.
```

---

### 6. ROI Calculator & Savings Dashboard

**Priority:** High
**Estimated Complexity:** Medium

```
Create a dedicated ROI & Savings page (/savings):

1. Investment Summary Card:
   - Total system cost input (editable, default Rs. 500,000)
   - Installation date picker
   - System capacity display

2. Lifetime Savings Counter:
   - Large animated counter showing total PKR saved since installation
   - Equivalent in: months of electricity bills, iPhone units, motorbikes (fun equivalents)

3. Break-even Progress:
   - Visual progress bar toward break-even
   - Estimated break-even date
   - Time remaining

4. Monthly Savings Chart:
   - Bar chart showing savings by month
   - Line overlay showing cumulative savings
   - Projection line to break-even

5. Projections Table:
   - 1 year, 5 year, 10 year, 25 year projected savings
   - Account for panel degradation (0.5% per year)
   - Include estimated tariff increases (10% annual inflation)

6. Achievement Badges:
   - First Rs. 10,000 saved
   - First month positive
   - 50% to break-even
   - Break-even achieved
   - Rs. 100,000 lifetime savings

Make numbers animate when they update. Use PKR currency throughout.
```

---

### 7. Notification Configuration System

**Priority:** High
**Estimated Complexity:** Medium

```
Create a comprehensive notification settings page (Settings > Notifications):

1. Notification Channels section:
   - Email toggle + email input
   - SMS toggle + phone number input (Pakistan format: +92-XXX-XXXXXXX)
   - In-App toggle (always on by default)
   - Quiet Hours: time range picker (e.g., 11 PM - 7 AM)

2. Alert Configuration table with toggles for each:

   Critical Alerts (default: all ON):
   - Device offline
   - Inverter fault
   - Battery fault
   - Grid failure

   Warning Alerts (default: all ON):
   - Low battery (with threshold slider: 10-50%)
   - High temperature (threshold: 40-60°C)
   - Performance drop (threshold: 10-50% below expected)
   - Communication unstable

   Informational Alerts (default: OFF except subscription):
   - Device back online
   - Daily summary
   - Weekly report ready
   - Subscription expiring (30 days before)
   - Firmware update available

3. Test Notification button that sends a test to selected channels.

4. Recent Notifications log at the bottom showing last 10 notifications sent.
```

---

### 8. User Management & Access Control

**Priority:** Medium
**Estimated Complexity:** Medium

```
Create a User Management page (Settings > Users) with role-based access:

1. Current User Card:
   - Show current user's role (Owner, Admin, Viewer)
   - Role description tooltip

2. Team Members List:
   - Name, Email, Role, Status (Active/Pending), Last Active
   - Edit role dropdown (Admin can't change Owner)
   - Remove user button with confirmation

3. Invite User Dialog:
   - Email input
   - Role selection (Admin, Viewer, Installer)
   - For Installer role: show duration picker (1 day, 3 days, 7 days, 30 days)
   - Custom message (optional)
   - Send Invite button

4. Pending Invitations section:
   - Show pending invites with expiry
   - Resend and Cancel buttons

5. Activity Log (collapsible):
   - Show user actions: who did what, when
   - Filter by user

Add role-based UI restrictions:
- Viewers can't access Settings > Configuration pages
- Only Owner can access Billing > Subscription
- Installers see special "Commissioning Mode" banner
```

---

### 9. Device Commissioning Flow

**Priority:** Medium
**Estimated Complexity:** High

```
Create an installer-focused device commissioning page (/commissioning):

1. Commissioning Mode banner at top (yellow background):
   - Show installer name and access expiry time
   - "Exit Commissioning" button

2. Step-by-step checklist UI:
   □ Device physically installed
   □ Device powered on
   □ Network connectivity verified
   □ Device registered in platform (with Add Device button)
   □ Communication test passed (with Run Test button)
   □ Basic telemetry received (shows preview of data)
   □ Configuration verified (shows key parameters)
   □ Owner notified / Handoff complete

3. Diagnostic Tools Panel:
   - Connection test button (shows latency, packet loss)
   - Signal strength indicator
   - Raw telemetry preview (collapsible JSON view)
   - Device info dump

4. Configuration Panel:
   - Device name
   - Polling interval (with subscription limit note)
   - Alert thresholds
   - Network settings (if applicable)

5. Handoff Section:
   - Owner email confirmation
   - Send handoff notification
   - Mark commissioning complete

Add prominent "Need Help?" button linking to installer support.
```

---

### 10. Enhanced Dashboard Customization

**Priority:** Medium
**Estimated Complexity:** Medium

```
Make the dashboard fully customizable:

1. Add "Edit Layout" button in dashboard header that enters edit mode.

2. In edit mode:
   - All widgets show drag handles
   - Widgets can be reordered by drag-and-drop
   - Show/hide toggles appear on each widget corner (X to hide)
   - "Add Widget" button opens widget picker

3. Widget Picker Drawer:
   - Categories: Statistics, Charts, Status, Actions
   - Available widgets with preview thumbnails:
     * Power Flow Diagram
     * Energy Chart (with period selector: Hour/Day/Week)
     * Billing Summary
     * Weather Widget
     * Quick Actions
     * Load Shedding Status
     * Goal Progress
     * Environmental Impact
     * Device Status Grid
     * Alerts Summary
     * Battery Status (large)
     * Today's Stats Row

4. Layout Persistence:
   - Save layout to localStorage (and later to backend)
   - Different layouts for mobile vs desktop
   - "Reset to Default" button

5. Widget Settings (gear icon on each widget):
   - Widget-specific options (e.g., chart time range, which stats to show)
```

---

### 11. PWA & Offline Support

**Priority:** Medium
**Estimated Complexity:** Medium

```
Implement Progressive Web App features:

1. Add manifest.json with:
   - App name: "Solar Hub"
   - Theme color: matching app primary color
   - Icons in multiple sizes
   - Start URL, display: standalone

2. Implement service worker for:
   - Caching static assets
   - Caching last known telemetry data
   - Queueing commands when offline

3. Add offline indicator:
   - Banner at top when offline: "You're offline. Showing cached data."
   - Timestamp of last data update
   - Reconnect button

4. Offline-available features:
   - View cached dashboard
   - View historical charts (cached)
   - View device list
   - Queue commands for later sync

5. Background sync:
   - When back online, show "Syncing..." indicator
   - Sync queued commands
   - Update telemetry data
   - Show "Sync complete" toast

6. Install prompt:
   - Show "Add to Home Screen" banner for mobile users
   - Custom install instructions dialog
```

---

### 12. AI Insights Panel

**Priority:** Medium
**Estimated Complexity:** Low

```
Create an AI Insights section on the dashboard:

1. Insights Card (collapsible):
   Header: "AI Insights" with sparkle icon

   Daily insight examples:
   - "You generated 25 kWh today, 10% above your monthly average 🎉"
   - "Your solar production peaked at 1:30 PM with 4.2 kW"
   - "You saved Rs. 520 today by using solar instead of grid"
   - "Consider running high-load appliances between 11 AM - 3 PM for maximum savings"

2. Anomaly Alerts:
   - "Generation was 20% lower than expected yesterday. Possible causes: cloudy weather, panel shading."
   - "Battery is charging slower than usual. Consider checking connections."
   - "Your consumption pattern changed this week. New appliance?"

3. Weekly Digest Card:
   - "This week: 156 kWh generated, Rs. 3,200 saved, 78% self-sufficiency"
   - Comparison with last week (arrow up/down)
   - Tip of the week

4. For now, use rule-based insights generated from mock data. Structure it so real AI integration is easy later.

5. "Thumbs up/down" feedback buttons on each insight.
```

---

### 13. Mobile-Optimized Improvements

**Priority:** Medium
**Estimated Complexity:** Low

```
Improve mobile experience:

1. Bottom Navigation Bar (already exists but enhance):
   - Home, Devices, Telemetry, Alerts, More
   - Show alert count badge on Alerts icon
   - Haptic feedback on tap (if supported)

2. Pull-to-refresh on main pages:
   - Dashboard, Telemetry, Devices
   - Show refresh animation
   - Update data on release

3. Swipe actions on list items:
   - Device list: swipe left to see telemetry, right for settings
   - Alert list: swipe right to dismiss

4. Mobile-optimized charts:
   - Larger touch targets
   - Simplified axis labels
   - Horizontal scroll for wide charts
   - Pinch-to-zoom

5. Quick Action Shortcuts (long-press on app icon):
   - View Dashboard
   - Check Battery Level
   - Today's Savings

6. Large touch-friendly buttons for critical actions:
   - Emergency stop (if battery control enabled)
   - Refresh data
   - Contact support
```

---

## Phase 2+ Prompts

### Reports Generation Page

```
Create a Reports page (/reports) with:

1. Report Types:
   - Daily Summary Report
   - Weekly Performance Report
   - Monthly Billing Report
   - Custom Date Range Report

2. Report Builder:
   - Date range picker
   - Select metrics to include (checkboxes)
   - Include charts toggle
   - Include raw data toggle

3. Export Options:
   - PDF download (styled report)
   - CSV download (raw data)
   - Excel download (formatted)
   - Email report (enter email addresses)

4. Scheduled Reports:
   - Enable/disable scheduling
   - Frequency: Daily, Weekly, Monthly
   - Day/time selection
   - Email recipients list
   - Save schedule

5. Report History:
   - List of previously generated reports
   - Download again button
   - Delete button
```

---

### Multi-Language Support (Urdu)

```
Add internationalization (i18n) support with English and Urdu:

1. Install and configure react-i18next

2. Create language files:
   - en.json (English - default)
   - ur.json (Urdu)

3. Key translations needed:
   - Navigation labels
   - Dashboard widget titles
   - Button labels
   - Form labels and placeholders
   - Error messages
   - Notification text

4. Language Switcher:
   - Dropdown in header or settings
   - Persist preference in localStorage
   - Flag icons for visual identification

5. RTL Support for Urdu:
   - Set dir="rtl" when Urdu selected
   - Mirror layouts appropriately
   - Handle mixed LTR/RTL content (numbers, technical terms)

6. Format localization:
   - Date formats (DD/MM/YYYY for Pakistan)
   - Number formats (lakhs, crores notation option)
   - Currency (Rs. prefix)
```

---

### Natural Language Query Interface

```
Add an "Ask Solar Hub" chat interface:

1. Floating chat button (bottom right corner)

2. Chat drawer that slides up with:
   - Input field: "Ask anything about your solar system..."
   - Send button
   - Recent queries list

3. Example queries to handle:
   - "How much did I generate today?"
   - "What are my savings this month?"
   - "When was my last outage?"
   - "Is my battery healthy?"
   - "Compare this week to last week"
   - "What's my best performing day?"

4. Response display:
   - Text response with relevant data
   - Quick chart if applicable
   - Links to relevant pages

5. For now, use keyword matching to handle queries. Structure for future AI/NLP integration.

6. "I don't understand" fallback with suggested queries.
```

---

## Implementation Priority

| Priority | Prompt | Rationale |
|----------|--------|-----------|
| 1 | Guided Setup Wizard | Critical for new user onboarding |
| 2 | Pakistani DISCO Tariff System | Core differentiator for Pakistan market |
| 3 | Enhanced Load Shedding Tracking | Critical for Pakistan market |
| 4 | Real-Time WebSocket Integration | Essential for live monitoring |
| 5 | Notification Configuration | Important for user engagement |
| 6 | What-If Scenario Calculator | High-value differentiator |
| 7 | ROI Calculator & Savings | Engagement and retention feature |
| 8 | User Management | Needed for multi-user scenarios |
| 9 | Device Commissioning | Important for installer workflow |
| 10 | Dashboard Customization | Polish feature |
| 11 | PWA & Offline Support | Important for Pakistani network conditions |
| 12 | AI Insights Panel | Differentiator, can be mock initially |
| 13 | Mobile Improvements | Polish feature |

---

## Usage Instructions

1. Copy one prompt at a time into Lovable
2. Let Lovable implement the feature
3. Test the implementation
4. Make any necessary adjustments
5. Move to the next prompt

**Tips for better results:**
- If a prompt is too complex, break it into smaller parts
- Provide feedback to Lovable if the output isn't quite right
- Reference existing components when asking for similar features
- Keep the tech stack consistent (React, TypeScript, Tailwind, shadcn/ui)

---

## Additional Prompts (Post-MVP Review)

The following prompts address features identified after the initial MVP implementation review.

### 14. System & Device Hierarchy Management

**Priority:** High
**Estimated Complexity:** High

**Background:** The data model for hierarchical device organization exists in mockData.ts but there's no UI to manage it. The hierarchy is: Home → Systems → [InverterArrays, BatteryArrays, Meters].

```
Create a comprehensive System & Device Hierarchy Management interface:

1. Replace the flat device list on /devices with a hierarchical tree view:
   - Toggle between "List View" (current) and "Hierarchy View" (new)
   - Hierarchy structure: Home → Systems → Arrays → Devices
   - Expandable/collapsible nodes with device counts
   - Color-coded by device type (inverters=solar, batteries=green, meters=blue)

2. Create System Management section in Settings > Systems (/settings/systems):
   - List of systems with name, device count, total capacity
   - "Add System" button opens dialog:
     * System name input
     * Description (optional)
     * Location within property (optional)
   - Edit/Delete system actions
   - Drag devices between systems

3. Array Management within each System:
   - "Add Inverter Array" / "Add Battery Array" buttons
   - Array configuration:
     * Array name (e.g., "North Roof Array", "Garage Battery Bank")
     * Capacity calculation (auto-summed from devices)
     * Configuration type (parallel/series for batteries)
   - Drag-and-drop devices into arrays

4. Device Assignment Flow:
   - Unassigned devices section at bottom
   - Drag device to system/array to assign
   - Context menu: "Move to..." with system/array picker
   - Batch selection for moving multiple devices

5. Visual System Topology:
   - Add "System Diagram" button that shows visual representation
   - Similar to existing VisualSystemDiagram but based on actual hierarchy
   - Show connections: which batteries serve which inverters
   - Click on component to see quick telemetry preview

6. Aggregated Metrics by Group:
   - System-level totals: total power, total energy today, overall status
   - Array-level totals: combined capacity, current output
   - Expand to see individual device metrics

7. Mobile Optimization:
   - Simplified tree view with horizontal scrolling
   - Bottom sheet for move/assign actions
   - Swipe left on device to access quick actions

Data is already structured in mockData.ts - connect the UI to use HomeHierarchy, System, InverterArray, and BatteryArray interfaces.
```

---

### 15. UI/UX Polish Improvements

**Priority:** Medium
**Estimated Complexity:** Low

```
Implement these UI/UX polish improvements across the application:

1. Loading States & Skeletons:
   - Add skeleton loaders to all data-fetching components
   - Dashboard widgets should show skeleton before data loads
   - Device cards should have skeleton state
   - Use subtle animation (shimmer effect) on skeletons

2. Empty States:
   - Create meaningful empty states for:
     * No devices yet → illustration + "Add your first device" CTA
     * No alerts → happy sun illustration + "All systems normal"
     * No outages this month → celebration illustration
     * Search with no results → helpful suggestions
   - Each empty state should have relevant action button

3. Micro-interactions:
   - Add subtle hover effects on all clickable cards
   - Button press animations (slight scale down)
   - Success checkmark animation on form submissions
   - Smooth transitions between page sections
   - Number counters should animate when values change

4. Error States & Recovery:
   - Error boundaries around major sections
   - Friendly error messages with retry button
   - "Something went wrong" page with helpful actions
   - Form validation with inline error messages
   - Automatic retry for transient failures

5. Contextual Help:
   - Add info icons (?) next to technical terms with tooltips
   - First-time user hints (dismissible)
   - "Learn more" links to relevant help content
   - Contextual tips based on user actions

6. Accessibility Improvements:
   - Ensure color contrast meets WCAG AA
   - Add aria-labels to icon-only buttons
   - Keyboard navigation for all interactive elements
   - Focus indicators visible in dark and light themes
   - Screen reader announcements for status changes

7. Performance Perception:
   - Optimistic UI updates (update UI before server confirms)
   - Progress indicators for long operations
   - Lazy load heavy components (charts)
   - Prefetch data on hover for likely next actions
```

---

### 16. Enhanced Device Details Page

**Priority:** Medium
**Estimated Complexity:** Medium

```
Create a comprehensive Device Details page (/devices/:deviceId):

1. Device Header:
   - Large device type icon with status indicator
   - Device name (editable inline)
   - Model and serial number
   - Status badge (Online/Offline/Warning/Commissioning)
   - "Last seen" timestamp

2. Quick Stats Row (device-type specific):
   - Inverter: Current Power, Today's Energy, Efficiency, Temperature
   - Battery: State of Charge, Current Power, Cycles, Health %
   - Meter: Import Power, Export Power, Net Energy, Power Factor

3. Real-time Telemetry Section:
   - Live values updating in real-time
   - Mini charts showing last 1 hour
   - Expand to full Telemetry page link

4. Device Information Card:
   - Manufacturer, Model, Firmware version
   - Installation date, Warranty expiry
   - Network info (IP, signal strength if applicable)
   - Edit button for user-configurable fields

5. Configuration Section:
   - Device-specific settings
   - Operating mode selector
   - Alert thresholds
   - Polling interval (with subscription limit note)

6. Maintenance Log:
   - List of maintenance events
   - Add maintenance record button
   - Types: Cleaning, Inspection, Repair, Firmware Update
   - Date, type, notes, next scheduled date

7. Performance History:
   - Daily/weekly/monthly performance summary
   - Comparison to similar devices (if multiple)
   - Efficiency trends
   - Anomaly highlights

8. Actions Panel:
   - Restart device (with confirmation)
   - Run diagnostics
   - Export device data
   - Remove device (with confirmation)
   - Move to different system/array

9. Related Devices:
   - Show other devices in same array/system
   - Quick navigation to related devices
```

---

### 17. Improved Navigation & Information Architecture

**Priority:** Medium
**Estimated Complexity:** Low

```
Improve navigation and information architecture:

1. Breadcrumb Navigation:
   - Add breadcrumbs on all sub-pages
   - Format: Home > Devices > Inverter 1 > Settings
   - Clickable each level

2. Global Search (Cmd+K / Ctrl+K):
   - Quick search dialog accessible from anywhere
   - Search across: devices, settings, help articles
   - Recent searches history
   - Quick actions: "go to billing", "add device"

3. Contextual Sidebar:
   - On desktop, show contextual info in sidebar
   - Related actions, quick links
   - Recent activity feed

4. Quick Navigation Shortcuts:
   - Keyboard shortcuts for power users:
     * G then D = Go to Dashboard
     * G then V = Go to Devices
     * G then T = Go to Telemetry
     * G then S = Go to Settings
   - Show shortcuts in command palette

5. Tab Memory:
   - Remember last selected tab on pages with tabs
   - Remember scroll position when navigating back
   - Remember filter states

6. Progressive Disclosure:
   - Default to Simple view
   - "Show more" for advanced options
   - User preference for default view

7. Notification Center Improvements:
   - Slide-out panel instead of full page
   - Group by type and day
   - Mark all as read
   - Filter by severity
```

---

## Updated Implementation Status (January 2026)

| Prompt | Status | Notes |
|--------|--------|-------|
| 1. Guided Setup Wizard | ✅ Implemented | 7-step wizard with tour |
| 2. Real-Time WebSocket | ✅ Implemented | useWebSocket hook, TelemetryContext |
| 3. Pakistani DISCO Tariff | ✅ Implemented | Full tariff system with slabs |
| 4. Load Shedding Tracking | ✅ Implemented | Dedicated /outages page |
| 5. What-If Calculator | ✅ Implemented | In billing page |
| 6. ROI & Savings | ✅ Implemented | /savings with achievements |
| 7. Notification Config | ⚠️ Partial | Basic settings, needs thresholds |
| 8. User Management | ✅ Implemented | /settings/users with roles |
| 9. Device Commissioning | ✅ Implemented | /commissioning flow |
| 10. Dashboard Customization | ✅ Implemented | Drag/drop, show/hide widgets |
| 11. PWA & Offline | ✅ Implemented | Service worker, offline banner |
| 12. AI Insights Panel | ✅ Implemented | Dashboard widget |
| 13. Mobile Improvements | ✅ Implemented | Swipe, pull-to-refresh |
| 14. Hierarchy Management | ❌ Not Started | Data model exists, no UI |
| 15. UI/UX Polish | ⚠️ Partial | Some areas need work |
| 16. Device Details Page | ⚠️ Partial | Basic settings, needs expansion |
| 17. Navigation Improvements | ⚠️ Partial | Basic navigation exists |

---

## Notes

- All currency values should use PKR (Rs.)
- Phone numbers should use Pakistan format (+92)
- Time zones should default to Asia/Karachi
- DISCO tariffs are based on NEPRA 2024 rates (update as needed)
- Mock data should reflect realistic Pakistani solar patterns

---

*Document created for Solar Hub Frontend Development*
*Last Updated: January 2026*
