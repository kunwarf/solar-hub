# Solar Monitoring & Remote Device Management Platform
## Comprehensive Requirements Specification

**Status:** Authoritative Requirements
**Version:** 2.0
**Scope:** MVP + Phase-1 + Phase-2 + Phase-3 (Corporate/Enterprise)
**Audience:** Product, Architecture, Engineering, Business
**Principle:** Requirements only - no implementation bias

---

## Table of Contents

1. [Purpose & Vision](#1-purpose--vision)
2. [Phase Overview](#2-phase-overview)
3. [User Model](#3-user-model)
4. [Core Architecture](#4-core-architecture)
5. [Device Communication Model](#5-device-communication-model)
6. [Device Identity & Authentication](#6-device-identity--authentication)
7. [Supported Device Types](#7-supported-device-types)
8. [Ease of Use Requirements](#8-ease-of-use-requirements)
9. [User Management & Access Control](#9-user-management--access-control)
10. [Installation & Commissioning](#10-installation--commissioning)
11. [Telemetry Requirements](#11-telemetry-requirements)
12. [Load Shedding & Outage Tracking](#12-load-shedding--outage-tracking)
13. [Command Execution](#13-command-execution)
14. [System Hierarchy Model](#14-system-hierarchy-model)
15. [Energy Billing & Simulation](#15-energy-billing--simulation)
16. [AI-Powered Features](#16-ai-powered-features)
17. [Reporting & Export](#17-reporting--export)
18. [Rich Dashboard & Visualization](#18-rich-dashboard--visualization)
19. [Device Lifecycle Management](#19-device-lifecycle-management)
20. [Subscription & Monetization Model](#20-subscription--monetization-model)
21. [Subscription Tiers & Feature Gating](#21-subscription-tiers--feature-gating)
22. [Frontend Requirements](#22-frontend-requirements)
23. [Security Requirements](#23-security-requirements)
24. [Non-Functional Requirements](#24-non-functional-requirements)
25. [Phase-2: Platform Maturity](#25-phase-2-platform-maturity)
26. [Phase-3: Corporate & Enterprise](#26-phase-3-corporate--enterprise)
27. [Out of Scope](#27-out-of-scope)
28. [Appendix: Phase Summary Matrix](#28-appendix-phase-summary-matrix)

---

## 1. Purpose & Vision

The platform is a subscription-based solar monitoring and remote device management system that enables users to securely monitor, control, optimize, and monetize solar energy systems.

### The system must:

- Support millions of simple users with one inverter
- Scale to advanced multi-device systems
- Provide secure, real-time telemetry and command execution
- Enable energy billing and AI-based battery optimization
- Evolve into a commercial SaaS platform with hardware dataloggers
- **Scale to corporate/enterprise deployments with multi-site management (Phase-3)**

---

## 2. Phase Overview

### MVP (Minimum Viable Product)
Core platform functionality to enable basic monitoring and control.

**Core Platform:**
- User authentication & authorization
- Device authentication with secure tokens
- Device communication (server-based architecture)
- Telemetry ingestion, storage & real-time delivery
- Basic command execution
- Default system hierarchy (auto-provisioned)
- Basic subscription enforcement
- User management & access control (Owner, Admin, Viewer, Installer)
- Alerts & notifications (Email, SMS, In-app)
- Installation & commissioning workflow

**Ease of Use (Differentiator):**
- Guided setup wizard (step-by-step first-time setup)
- Smart defaults (pre-configured settings that "just work")
- One-click actions for common tasks
- Contextual help (tooltips, inline explanations)
- Simple/Advanced mode toggle
- Quick status view (glanceable "everything OK" indicator)
- Offline-first PWA (works with poor connectivity)

**Rich Dashboards (Differentiator):**
- Power flow animation (solar → battery → load → grid)
- Customizable widget layout
- Comparison views (today vs yesterday, this month vs last)
- Goal tracking (savings goals with progress)
- Environmental impact display (CO2 saved, trees equivalent)
- At-a-glance health indicator (Green/Yellow/Red)
- Trends & patterns visualization

**AI-Powered Features (Differentiator):**
- Anomaly detection (detect faults before they happen)
- Generation forecasting (predict solar output)
- Consumption pattern analysis
- Personalized insights ("You used 20% more than usual")
- AI-based battery charging/discharging optimization

**Utility Billing Simulation (Differentiator):**
- Energy billing calculations
- What-if scenarios ("What if I add 2 more panels?")
- Tariff comparison ("Which plan saves me more?")
- ROI calculator (investment payback period)
- Bill reconciliation (simulated vs actual DISCO bill)
- Savings tracker (month-over-month, year-over-year)
- Break-even projection
- Net metering credit tracking

**Local Market Features (Pakistan):**
- Grid outage / load shedding tracking
- Outage duration reports & history
- Battery backup utilization during outages
- Pre-loaded DISCO tariffs (LESCO, K-Electric, MEPCO, etc.)
- Slab-based billing support
- Net metering support per NEPRA rules
- Local date/time formats, PKR currency
- Low bandwidth optimization
- SMS notifications (high priority)
- JazzCash & EasyPaisa payment integration

### Phase-1 (Commercial Release)
Enhanced features for scale and monetization.

- Subscription tiers with feature gating
- Higher-frequency telemetry (paid tiers)
- Reporting & export (PDF, CSV, Excel)
- Scheduled reports with email delivery
- Device lifecycle management (OTA updates, replacement)
- Advanced hierarchy editing (for advanced users)
- Predictive maintenance alerts
- Bank transfer & card payment options
- Fuel price adjustment (FPA) tracking
- Industrial ToU tariffs

### Phase-2 (Platform Maturity)
Platform hardening and expanded capabilities.

- Mobile applications (iOS, Android)
- Data privacy & compliance (GDPR)
- SLA & availability guarantees
- Support & customer service integration
- White-label / reseller model
- Advanced analytics & insights
- Third-party integrations & webhooks
- Urdu language support (bilingual interface)
- WhatsApp notifications
- Natural language queries ("How much did I save?")

### Phase-3 (Corporate & Enterprise)
Enterprise-grade features for large organizations.

- Multi-site corporate accounts
- Centralized corporate dashboard
- Cross-site reporting & analytics
- Corporate billing & cost allocation
- Fleet management
- Role hierarchy for organizations
- API access for enterprise integrations
- Custom SLAs & dedicated support

---

## 3. User Model

### 3.1 User Types (Configuration-Level)

> **Important:** Basic vs Advanced users differ only in how systems are configured, not in available features.

#### Basic User
- System hierarchy is auto-created
- No manual hierarchy building required
- UI hides complex configuration
- All subscription features are available

#### Advanced User
- Can manually define and edit system hierarchy
- Can manage multiple systems, arrays, and attachments
- Same features as basic user
- Full configuration UI exposed

### 3.2 User Roles (Access-Level) [MVP]

| Role | Description | Permissions |
|------|-------------|-------------|
| **Owner** | System owner, full control | All permissions, billing, delete system, transfer ownership |
| **Admin** | Delegated administrator | Manage devices, users, settings (no billing access) |
| **Viewer** | Read-only access | View dashboard, telemetry, reports only |
| **Installer** | Temporary technical access | Setup, configure, test devices (time-limited) |

---

## 4. Core Architecture

### 4.1 Two-Backend Architecture (Mandatory)

#### System A - Platform & Monitoring Backend

Responsibilities:
- User authentication & session management
- Subscription management & enforcement
- Configuration & hierarchy management
- APIs for telemetry, commands, billing, scheduler
- Frontend-facing backend
- Business logic & rules engine

#### System B - Communication & Telemetry Backend

Responsibilities:
- Acts as communication server
- Accepts device connections (devices are clients)
- Authenticates devices using tokens
- Controls polling frequency & command execution
- Enforces subscription-based limits
- Telemetry ingestion & forwarding

### 4.2 Backend Communication

- System A and System B communicate via internal APIs
- System B reports device status to System A
- System A issues commands through System B
- Clear separation of concerns between backends

---

## 5. Device Communication Model

### 5.1 Client-Server Rule (Hard Requirement)

| Component | Role |
|-----------|------|
| Communication System (System B) | **Server** |
| Devices / Gateways / Dataloggers | **Clients** |

### 5.2 Device Connection Behavior

Devices must:
- Initiate outbound connections to the server
- Maintain persistent sessions (reconnect on disconnect)
- Never accept inbound connections
- Handle connection loss gracefully

### 5.3 Benefits

- NAT/CGNAT compatibility (works behind any router)
- Security isolation (no open ports on devices)
- Cloud scalability (standard load balancing)
- Firewall-friendly deployment

---

## 6. Device Identity & Authentication

### 6.1 Device Identity [MVP]

Each device or datalogger has:
- **Unique serial number** (hardware identifier)
- **Platform device ID** (logical identifier in system)
- **Device type** (inverter, battery, meter, datalogger)

### 6.2 Device Authentication [MVP]

Requirements:
- Separate from user authentication
- Unique credentials per device (no shared secrets)
- Time-based tokens with expiry
- Token rotation support
- Revocation capability
- Secure credential provisioning during commissioning

### 6.3 Authentication Flow

1. Device connects to System B
2. Device presents credentials/token
3. System B validates token
4. Session established or rejected
5. Token refresh as needed

---

## 7. Supported Device Types

### 7.1 Device Categories

| Device Type | Phase | Description |
|-------------|-------|-------------|
| Solar Inverters | MVP | Grid-tie, hybrid, off-grid inverters |
| Batteries | MVP | Lithium, lead-acid storage systems |
| Energy Meters | MVP | Grid meters, consumption meters |
| Dataloggers | Phase-1 | Custom gateway devices |
| Smart Loads | Phase-2+ | Controllable loads (future) |

### 7.2 Supported Protocols

| Protocol | Phase | Use Case |
|----------|-------|----------|
| Modbus TCP/IP | MVP | Inverters, meters, batteries |
| MQTT | MVP | Dataloggers, IoT devices |
| Modbus RTU (via gateway) | Phase-1 | Legacy devices |
| Custom protocols | Phase-2+ | Proprietary devices |

---

## 8. Ease of Use Requirements

> **This is a core differentiator. Every feature must prioritize simplicity.**

### 8.1 Guided Setup Wizard [MVP]

First-time user experience:

| Step | Description |
|------|-------------|
| 1. Welcome | Brief intro, value proposition |
| 2. Account Setup | Basic profile, location |
| 3. Add First Device | QR scan or code entry |
| 4. Verify Connection | Automated connection test |
| 5. Configure Basics | Tariff selection, goals |
| 6. Dashboard Tour | Highlight key features |
| 7. Complete | Ready to use |

Requirements:
- Skip-able for experienced users
- Progress indicator
- Can resume if interrupted
- Context-sensitive help at each step

### 8.2 Smart Defaults [MVP]

System must provide intelligent defaults:

| Setting | Default Behavior |
|---------|------------------|
| Polling Interval | 60 seconds (subscription max) |
| Alert Thresholds | Industry-standard safe values |
| Battery Reserve | 20% minimum SOC |
| Notification Preferences | Critical alerts ON, info OFF |
| Dashboard Layout | Optimized for most common use |
| Tariff | Auto-detect from location if possible |

Requirements:
- User can override any default
- Defaults clearly indicated in UI
- "Reset to defaults" option available

### 8.3 One-Click Actions [MVP]

Common tasks accessible in single tap:

| Action | Description |
|--------|-------------|
| Quick Status | "Is everything OK?" answer |
| Today's Summary | Generation, savings, issues |
| Force Sync | Refresh all device data |
| Emergency Stop | Stop battery discharge (if applicable) |
| Share Report | Send today's summary via SMS/email |
| Contact Support | Direct support access |

### 8.4 Simple/Advanced Mode Toggle [MVP]

Requirements:
- Global toggle in settings
- Persisted per user
- Simple mode hides:
  - Technical parameters
  - Advanced configuration
  - Raw telemetry values
  - Developer options
- Advanced mode shows:
  - Full device parameters
  - Hierarchy editing
  - Raw data access
  - API settings

### 8.5 Contextual Help [MVP]

Requirements:
- Tooltips on all non-obvious UI elements
- "What's this?" links to explanations
- In-context examples where applicable
- No jargon in user-facing text
- Help content searchable

### 8.6 Quick Status Indicators [MVP]

At-a-glance system health:

| Indicator | Meaning |
|-----------|---------|
| Green | All systems normal |
| Yellow | Attention needed (warning) |
| Red | Action required (critical) |
| Gray | Offline / No data |

Requirements:
- Visible on all main screens
- Tap to see details
- Clear explanation of status reason

### 8.7 Offline-First PWA [MVP]

Requirements:
- App works without internet (cached data)
- Queued actions sync when online
- Clear offline indicator
- Graceful degradation of features
- Background sync when connection restored
- Works on low-bandwidth connections (2G/3G)

---

## 9. User Management & Access Control

### 9.1 Multi-User Access [MVP]

Requirements:
- Multiple users can access a single system
- Each user has a defined role (Owner, Admin, Viewer, Installer)
- One Owner per system (mandatory)
- Owner can transfer ownership to another user
- Users can belong to multiple systems

### 9.2 User Invitation Flow [MVP]

1. Owner/Admin initiates invitation via email
2. Invitee receives email with invitation link
3. Invitee creates account (if new) or accepts (if existing)
4. Access granted with specified role
5. Inviter notified of acceptance

### 9.3 Access Management [MVP]

Requirements:
- Revoke access anytime (immediate effect)
- Change user roles (Owner can change any, Admin cannot change Owner)
- View list of users with access
- Activity log per user (audit trail)

### 9.4 Installer Access [MVP]

Special requirements for installer role:
- Time-limited access (configurable: hours/days)
- Auto-expire after duration
- Can be extended by Owner/Admin
- Access revoked after commissioning complete
- Separate installer invitation flow

---

## 9. Installation & Commissioning

### 9.1 Device Onboarding [MVP]

#### Activation Methods

| Method | Description |
|--------|-------------|
| Activation Code | Unique alphanumeric code per device |
| QR Code Scan | QR code on device label (encodes activation code) |
| Serial Number Entry | Manual entry with verification |

#### Onboarding Flow

1. User/Installer initiates "Add Device"
2. Scan QR code or enter activation code
3. System validates code and device eligibility
4. Device capabilities auto-discovered
5. Device linked to user's system
6. Confirmation displayed

### 9.2 Installer Mode [MVP]

Requirements:
- Dedicated installer access (not regular user flow)
- Installation checklist/wizard UI
- Step-by-step commissioning process
- Connection test & verification tools
- Signal strength / communication quality indicator
- Device configuration interface
- Handoff to owner after completion

### 9.3 Commissioning Checklist [MVP]

Mandatory steps:
- [ ] Device physically installed
- [ ] Device powered on
- [ ] Network connectivity verified
- [ ] Device registered in platform
- [ ] Communication test passed
- [ ] Basic telemetry received
- [ ] Owner notified / handoff complete

### 9.4 Verification Tests [MVP]

| Test | Description |
|------|-------------|
| Connectivity Test | Verify device can reach server |
| Authentication Test | Verify device credentials work |
| Telemetry Test | Verify data is being received |
| Command Test | Verify commands can be executed |

---

## 10. Telemetry Requirements

### 10.1 Polling Frequency [MVP]

#### Default Behavior
- **Default polling interval: 60 seconds**
- Applies to all users, devices, and systems
- This is the base subscription entitlement

#### Subscription-Based Frequency [Phase-1]

| Tier | Polling Interval | Use Case |
|------|------------------|----------|
| Base | 60 seconds | Standard monitoring |
| Enhanced | 30 seconds | Better responsiveness |
| Premium | 10 seconds | Near real-time |
| Enterprise | 5 seconds | Critical systems (Phase-3) |

### 10.2 Frequency Enforcement [MVP]

Rules:
- Enforcement happens only in Communication System (System B)
- User-configured interval validated against subscription
- If requested interval < allowed interval: reject or auto-adjust
- UI must clearly indicate subscription limits
- Even if device sends faster, System B throttles ingestion

### 10.3 Telemetry Data Handling [MVP]

Requirements:
- All telemetry timestamped (device time + server time)
- Device-scoped and system-scoped storage
- Stored in time-series database
- Aggregated hourly and daily
- Raw data retention based on subscription tier

### 10.4 Real-Time Telemetry [MVP]

Requirements:
- Logged-in users receive near-real-time updates
- Data flow: Device -> System B -> System A -> UI
- UI never connects directly to devices
- WebSocket or Server-Sent Events for push updates
- Graceful fallback if real-time unavailable

### 10.5 Telemetry Data Points

#### Inverter Telemetry
- AC output power (W)
- AC voltage, current, frequency
- DC input power, voltage, current (per MPPT)
- Daily/total energy generation (kWh)
- Operating status / mode
- Fault codes
- Temperature

#### Battery Telemetry
- State of Charge (SOC) %
- Voltage, current
- Charge/discharge power (W)
- Temperature
- Cycle count
- Health status
- Fault codes

#### Meter Telemetry
- Grid import/export power (W)
- Voltage, current per phase
- Power factor
- Frequency
- Daily/total energy (import/export)

---

## 11. Alerts & Notifications

### 11.1 Alert Types [MVP]

#### Critical Alerts
| Alert | Trigger | Priority |
|-------|---------|----------|
| Device Offline | No communication for X minutes | High |
| Inverter Fault | Fault code received | High |
| Battery Fault | Battery error/alarm | High |
| Grid Failure | Grid unavailable (for grid-tie) | High |

#### Warning Alerts
| Alert | Trigger | Priority |
|-------|---------|----------|
| Low Battery | SOC below threshold | Medium |
| High Temperature | Device temp above limit | Medium |
| Performance Drop | Generation below expected | Medium |
| Communication Unstable | Frequent disconnects | Medium |

#### Informational Alerts
| Alert | Trigger | Priority |
|-------|---------|----------|
| Device Online | Device reconnected | Low |
| Subscription Expiring | X days before expiry | Low |
| Firmware Update Available | New version detected | Low |
| Daily Summary | End of day report | Low |

### 11.2 Notification Channels [MVP]

| Channel | Phase | Description |
|---------|-------|-------------|
| In-App | MVP | Notification center in dashboard |
| Email | MVP | Email to registered address |
| SMS | MVP | Text messages (high priority for Pakistan) |
| Push Notification | Phase-2 | Mobile app push |
| Webhook | Phase-2 | HTTP callback for integrations |
| WhatsApp | Phase-2 | WhatsApp Business API integration |

### 11.3 Notification Configuration [MVP]

User can configure:
- Enable/disable per alert type
- Enable/disable per channel
- Configurable thresholds (where applicable)
- Quiet hours (no notifications during specified times)
- Alert recipients (which users receive which alerts)

### 11.4 Alert History [MVP]

Requirements:
- All alerts logged with timestamp
- Alert history viewable in UI
- Filter by type, severity, date range
- Acknowledge/dismiss functionality
- Unacknowledged alert indicators

---

## 12. Load Shedding & Outage Tracking

> **Critical feature for Pakistan market. This is a key differentiator.**

### 12.1 Grid Availability Monitoring [MVP]

Requirements:
- Real-time grid status detection (ON/OFF)
- Grid status from inverter/meter telemetry
- Immediate status change detection
- Grid quality metrics (voltage stability)

### 12.2 Outage Event Logging [MVP]

For each outage event, record:

| Data Point | Description |
|------------|-------------|
| Start Time | When grid went offline |
| End Time | When grid restored |
| Duration | Total outage duration |
| Type | Scheduled vs unscheduled (if known) |
| Impact | Battery usage during outage |

### 12.3 Outage Reports & Analytics [MVP]

| Report | Description |
|--------|-------------|
| Daily Outage Summary | Number of outages, total duration |
| Weekly/Monthly Report | Outage trends, patterns |
| Outage Calendar | Visual calendar view of outages |
| Average Outage Duration | Statistical analysis |
| Peak Outage Times | When outages most likely occur |

### 12.4 Battery Backup Utilization [MVP]

Track during outages:
- Battery energy consumed during outage
- Backup duration provided
- Loads sustained during outage
- Battery SOC at outage start/end
- "Survived outage" vs "Battery depleted" status

### 12.5 Outage Alerts [MVP]

| Alert | Trigger |
|-------|---------|
| Grid Down | Grid power lost |
| Grid Restored | Grid power returned |
| Long Outage Warning | Outage exceeds X minutes |
| Low Battery During Outage | SOC dropping during outage |
| Battery Depleted | Battery exhausted during outage |

### 12.6 UPS/Inverter Mode Tracking [MVP]

Track inverter operating mode:
- Grid-tie mode (normal)
- Backup/UPS mode (outage)
- Hybrid mode
- Mode switch timestamps
- Time spent in each mode

### 12.7 Outage Impact Analysis [MVP]

Show user:
- "Your solar + battery provided X hours of backup"
- "You avoided X hours of darkness"
- "Estimated value of backup: Rs. X"
- Comparison with neighbors (anonymized, future)

---

## 13. Command Execution

### 13.1 Command Flow [MVP]

1. User issues command via UI/API
2. Platform validates user authorization
3. Platform validates subscription allows command
4. Command queued and forwarded to System B
5. System B executes command on device
6. Device responds with result
7. Result logged and returned to user

### 13.2 Command Types

| Command Category | Examples | Phase |
|------------------|----------|-------|
| Read Parameters | Read settings, status | MVP |
| Write Parameters | Change settings | MVP |
| Control Actions | Start, stop, reset | MVP |
| Scheduling | Set charge/discharge times | Phase-1 |
| Firmware | Initiate OTA update | Phase-1 |

### 13.3 Command Requirements [MVP]

- **Auditable**: Log who, when, what, result
- **Rate-limited**: Prevent command flooding
- **Idempotent**: Where possible, same command = same result
- **Validated**: Check parameters before execution
- **Read-back**: Verify write commands took effect
- **Timeout**: Commands expire if not executed in time

### 13.4 Command Authorization [MVP]

| Role | Read Commands | Write Commands | Control Commands |
|------|---------------|----------------|------------------|
| Owner | Yes | Yes | Yes |
| Admin | Yes | Yes | Yes |
| Viewer | Yes | No | No |
| Installer | Yes | Yes | Yes (during commissioning) |

---

## 14. System Hierarchy Model

### 14.1 Conceptual Hierarchy [MVP]

```
User Account
└── System (Home / Site)
    ├── Inverter Groups (Arrays)
    │   └── Inverters
    ├── Battery Groups
    │   └── Batteries
    ├── Energy Meters
    │   └── Grid Meter
    │   └── Consumption Meter
    └── Attachments (Battery <-> Inverter links)
```

### 14.2 Hierarchy Rules [MVP]

- A user can have multiple systems
- A system belongs to one primary user (Owner)
- Devices belong to exactly one system
- Devices can be grouped logically
- Attachments define relationships (e.g., which battery serves which inverter)

### 14.3 Auto-Provisioning [MVP]

For basic users:
- Default system created on first device registration
- Default groups created automatically
- Devices added to default groups
- No manual configuration required

### 14.4 Advanced Editing [Phase-1]

For advanced users:
- Create/rename/delete systems
- Create/rename/delete groups
- Move devices between groups
- Define custom attachments
- Multi-system management

---

## 15. Energy Billing & Simulation

> **This is a core differentiator. Comprehensive billing simulation with what-if analysis.**

### 15.1 Purpose [MVP]

Calculate and display:
- Energy consumption
- Grid import/export
- Solar self-consumption
- Estimated savings
- Estimated bills
- What-if projections

### 15.2 Billing Calculations [MVP]

Requirements:
- Support single inverter systems
- Support complex multi-device systems
- Time-of-Use (ToU) tariff support
- Flat rate tariff support
- Tiered/slab tariff support (Pakistan standard)
- Fixed charges (monthly fees, taxes)
- Net metering calculations
- Fuel Price Adjustment (FPA) tracking

### 15.3 Tariff Configuration [MVP]

User can configure:
- Tariff type (flat, ToU, tiered/slab)
- Rate values per tier/time
- Currency (PKR default)
- Billing cycle (monthly, bi-monthly)
- Fixed charges
- Net metering export rate

Pre-loaded tariffs:
- LESCO (Lahore)
- K-Electric (Karachi)
- MEPCO (Multan)
- IESCO (Islamabad)
- PESCO (Peshawar)
- FESCO (Faisalabad)
- Other DISCOs

### 15.4 Billing Data Display [MVP]

Show user:
- Current billing period usage (kWh)
- Grid import vs export breakdown
- Projected bill amount
- Historical bills (past 12 months)
- Savings vs grid-only scenario
- Export earnings (net metering credits)
- Month-over-month comparison
- Year-over-year comparison

### 15.5 Bill Reconciliation [MVP]

Requirements:
- Compare simulated bill vs actual DISCO bill
- Identify discrepancies
- Track accuracy over time
- Adjust tariff settings based on actual bills

### 15.6 What-If Scenarios (Differentiator) [MVP]

| Scenario | Description |
|----------|-------------|
| Add Panels | "What if I add 2 more panels?" |
| Add Battery | "What if I add battery storage?" |
| Increase Capacity | "What if I upgrade to 10kW system?" |
| Change Tariff | "Which tariff plan saves me more?" |
| Load Changes | "What if my consumption increases?" |

Requirements:
- User inputs hypothetical changes
- System calculates projected impact
- Show side-by-side comparison (current vs projected)
- Display ROI and payback period
- Recommend optimal configuration

### 15.7 ROI Calculator [MVP]

Calculate and display:
- Total system investment cost
- Monthly savings
- Annual savings
- Break-even point (months/years)
- 5-year / 10-year / 25-year projections
- Return on investment percentage

### 15.8 Savings Tracker [MVP]

Track and display:
- Lifetime savings (since installation)
- Monthly savings history
- Savings goals (user-defined)
- Progress towards goals
- Savings milestones and achievements

### 15.9 Environmental Impact [MVP]

Calculate and display:
- CO2 emissions avoided (kg)
- Equivalent trees planted
- Equivalent car miles saved
- Clean energy generated (kWh)
- Environmental impact certificates (shareable)

---

## 16. AI-Powered Features

> **This is a core differentiator. AI should make the system smarter and more valuable.**

### 16.1 AI Battery Optimization [MVP]

#### Goal
> **Maximize self-reliance, not energy trading.**

Optimize battery charge/discharge to:
- Minimize grid dependence
- Maximize solar self-consumption
- Reduce electricity bills
- Extend battery life

#### Optimization Inputs

| Input | Source |
|-------|--------|
| Solar generation forecast | Historical + weather API |
| Load consumption patterns | Historical telemetry |
| Battery state (SOC, health) | Real-time telemetry |
| Grid availability | Real-time status |
| Tariff structure | User configuration |
| User preferences | Settings |
| Weather forecast | External API |

#### Optimization Outputs

- Charge/discharge schedule
- Recommended SOC targets
- Grid import/export timing
- Mode switching commands
- Explanation of decisions

#### Requirements

- **User Overrideable**: User can override AI decisions
- **Safe by Default**: Conservative decisions if uncertain
- **Explainable**: Show why decisions were made
- **Adaptive**: Learn from actual outcomes
- **Respect Constraints**: Battery limits, user preferences

#### Optimization Modes

| Mode | Description |
|------|-------------|
| Auto | AI makes all decisions |
| Scheduled | User-defined schedule, AI fills gaps |
| Manual | User controls everything |
| Eco | Maximize savings |
| Backup | Prioritize backup reserve |

### 16.2 Anomaly Detection [MVP]

Detect issues before they become problems:

| Anomaly Type | Detection Method |
|--------------|------------------|
| Generation Drop | Compare actual vs expected output |
| Inverter Degradation | Efficiency trending below baseline |
| Battery Health Decline | Capacity/cycle degradation patterns |
| Communication Issues | Connection stability patterns |
| Unusual Consumption | Load patterns outside normal range |

Requirements:
- Real-time anomaly scoring
- Historical baseline comparison
- Severity classification (low/medium/high)
- Actionable recommendations
- Alert generation for significant anomalies

### 16.3 Generation Forecasting [MVP]

Predict solar generation:

| Forecast | Description |
|----------|-------------|
| Today | Hourly forecast for current day |
| Tomorrow | Next day prediction |
| 7-Day | Week ahead outlook |

Inputs:
- Historical generation data
- Weather forecast (cloud cover, temperature)
- Panel specifications
- Seasonal patterns

Requirements:
- Accuracy tracking (forecast vs actual)
- Confidence intervals
- Update forecasts as weather changes
- Display in user-friendly format

### 16.4 Consumption Pattern Analysis [MVP]

Learn and predict user's energy consumption:

| Pattern | Description |
|---------|-------------|
| Daily Profile | Typical hourly consumption |
| Weekly Pattern | Weekday vs weekend differences |
| Seasonal Trends | Summer vs winter patterns |
| Peak Hours | When consumption is highest |
| Base Load | Minimum constant consumption |

Use cases:
- Optimize battery scheduling
- Alert on unusual consumption
- Size recommendations for upgrades
- Tariff optimization suggestions

### 16.5 Personalized Insights [MVP]

Generate user-friendly insights:

| Insight Type | Example |
|--------------|---------|
| Daily Summary | "You generated 25 kWh today, 10% above average" |
| Savings Alert | "You saved Rs. 500 this week vs grid power" |
| Performance Tip | "Your panels performed better in the morning" |
| Anomaly Notice | "Generation was 20% lower than expected yesterday" |
| Achievement | "You've reached 1 MWh of clean energy!" |

Requirements:
- Plain language (no jargon)
- Actionable where possible
- Positive framing
- Delivered via dashboard, notifications
- Frequency configurable by user

### 16.6 Predictive Maintenance [Phase-1]

Predict equipment issues before failure:

| Prediction | Indicators |
|------------|------------|
| Inverter Service Needed | Efficiency decline, error frequency |
| Panel Cleaning Required | Generation vs expected gap |
| Battery Replacement | Capacity degradation trend |
| Connection Issues | Intermittent communication |

Requirements:
- Confidence score for predictions
- Recommended actions
- Service provider integration (future)
- Maintenance history tracking

---

## 17. Reporting & Export

### 17.1 Standard Reports [Phase-1]

| Report | Frequency | Content |
|--------|-----------|---------|
| Daily Summary | Daily | Generation, consumption, savings |
| Weekly Report | Weekly | Week overview, trends |
| Monthly Report | Monthly | Full month analysis, billing |
| Performance Report | On-demand | System performance metrics |

### 17.2 Report Content [Phase-1]

Reports include:
- Energy generation (solar)
- Energy consumption
- Grid import/export
- Battery cycles
- Self-consumption ratio
- Savings calculation
- Comparison with previous period
- Alerts/events summary

### 17.3 Export Formats [Phase-1]

| Format | Use Case |
|--------|----------|
| PDF | Printable reports, sharing |
| CSV | Data analysis, spreadsheets |
| Excel (XLSX) | Advanced analysis |
| JSON | API/integrations (Phase-2) |

### 17.4 Export Scope [Phase-1]

User can export:
- Telemetry data (date range selection)
- Reports (specific report or date range)
- Alert history
- Command audit log

### 17.5 Scheduled Reports [Phase-1]

Requirements:
- Schedule automatic report generation
- Email delivery to specified addresses
- Configurable frequency (daily, weekly, monthly)
- Enable/disable per report type

---

## 18. Rich Dashboard & Visualization

> **This is a core differentiator. Dashboards must be intuitive and visually compelling.**

### 18.1 Power Flow Visualization [MVP]

Animated energy flow diagram showing:
- Solar generation (panels → system)
- Battery flow (charge/discharge direction)
- Grid flow (import/export)
- Load consumption
- Real-time power values on each flow

Requirements:
- Animated flow lines showing direction
- Color coding (green = solar, blue = grid, orange = battery)
- Real-time updates (every few seconds)
- Tap on any component for details
- Works on mobile and desktop

### 18.2 Dashboard Widgets [MVP]

| Widget | Description |
|--------|-------------|
| Power Flow | Animated energy flow diagram |
| Current Status | System health indicator |
| Today's Generation | Solar kWh with comparison |
| Today's Consumption | Load kWh |
| Battery Status | SOC%, charge/discharge |
| Grid Status | Import/export, on/off |
| Savings Today | Rs. saved |
| Weather | Current + forecast |
| Alerts | Active alerts count |
| Quick Actions | Common controls |

### 18.3 Customizable Layout [MVP]

Requirements:
- User can rearrange widgets
- User can show/hide widgets
- Layout saved per user
- Different layouts for mobile/desktop
- Reset to default option

### 18.4 Comparison Views [MVP]

| Comparison | Description |
|------------|-------------|
| Today vs Yesterday | Side-by-side daily comparison |
| This Week vs Last Week | Weekly comparison |
| This Month vs Last Month | Monthly comparison |
| This Year vs Last Year | Annual comparison |
| Actual vs Expected | Performance comparison |

Requirements:
- Visual charts (bar, line)
- Percentage change indicators
- Color coding (green = improvement, red = decline)

### 18.5 Historical Charts [MVP]

| Chart Type | Time Ranges |
|------------|-------------|
| Generation | Hour, day, week, month, year |
| Consumption | Hour, day, week, month, year |
| Battery SOC | Hour, day, week |
| Grid Import/Export | Hour, day, week, month |
| Savings | Day, week, month, year |

Requirements:
- Interactive charts (zoom, pan)
- Multiple data series overlay
- Export chart as image
- Date range picker

### 18.6 Goal Tracking [MVP]

Users can set and track goals:

| Goal Type | Example |
|-----------|---------|
| Monthly Savings | "Save Rs. 5,000 this month" |
| Self-Sufficiency | "80% solar self-consumption" |
| Generation Target | "Generate 500 kWh this month" |
| Environmental | "Offset 100kg CO2 this month" |

Requirements:
- Visual progress indicator
- Notifications on milestone achievement
- Goal history
- Suggestions for achievable goals

### 18.7 Environmental Impact Display [MVP]

Show in compelling visuals:
- CO2 avoided (with equivalents)
- Trees equivalent
- Cars off road equivalent
- Homes powered equivalent
- Lifetime clean energy generated

Requirements:
- Animated/engaging display
- Shareable as image/social media
- Certificate generation
- Running totals + period totals

---

## 19. Device Lifecycle Management

### 19.1 Firmware Updates [Phase-1]

#### OTA Update Capability
Requirements:
- Detect available firmware updates
- Display update notifications
- User-initiated update trigger
- Automatic updates (optional, user preference)
- Update scheduling (off-peak hours)
- Progress tracking
- Rollback support on failure
- Update history log

#### Update Safety
- Verify firmware integrity (checksum)
- Verify compatibility before update
- Maintain minimum battery level during update
- Graceful handling of update failures

### 19.2 Device Replacement [Phase-1]

#### Replacement Flow
1. User initiates replacement process
2. Old device deactivated
3. New device registered
4. Historical data linked to new device (optional)
5. Configuration transferred (where applicable)
6. Old device marked as decommissioned

#### Data Handling
- Option to retain historical data under new device
- Option to archive old device data separately
- Clear audit trail of replacement

### 19.3 Device Decommissioning [Phase-1]

Requirements:
- Remove device from active monitoring
- Revoke device credentials
- Archive historical data (retention policy)
- Clear device from hierarchy
- Audit log entry

### 19.4 Device Health Monitoring [Phase-1]

Track:
- Communication reliability (uptime %)
- Error/fault frequency
- Performance degradation trends
- Warranty status (if available)

---

## 20. Subscription & Monetization Model

### 20.1 Subscription-Based Platform [MVP]

- Platform access requires active subscription
- Subscription tied to user account
- Covers all systems under account

### 20.2 Pricing Model [MVP]

#### Base Pricing
- **Rs. 200 / month** base price
- Covers: 1 inverter + 1 battery

#### Usage-Based Pricing
Subscription cost based on:
- Number of inverters
- Number of batteries
- Telemetry polling frequency tier (Phase-1)
- Feature add-ons (Phase-1)

#### Pricing Formula (Conceptual)
```
Subscription Cost =
  (Base price per inverter × Inverter count)
  + (Base price per battery × Battery count)
  × Frequency multiplier
  + Optional feature add-ons
```

### 20.3 Subscription Lifecycle [MVP]

| State | Description | System Behavior |
|-------|-------------|-----------------|
| Active | Payment current | Full access |
| Past-due | Payment overdue | Grace period, warnings |
| Suspended | Grace period expired | Limited/no access |
| Cancelled | Subscription ended | No access, data retained |

### 20.4 Enforcement Policy [MVP]

Two enforcement modes (configurable per deployment):

| Mode | Behavior |
|------|----------|
| Soft | Limited functionality (read-only, no commands) |
| Hard | Device communication blocked |

### 20.5 Payment Methods [MVP]

#### Mobile Wallets (Priority for Pakistan)

| Provider | Priority | Integration |
|----------|----------|-------------|
| JazzCash | High | Payment API |
| EasyPaisa | High | Payment API |
| SadaPay | Medium | Future |
| NayaPay | Medium | Future |

#### Other Payment Methods

| Method | Phase |
|--------|-------|
| Bank Transfer | Phase-1 |
| Credit/Debit Card | Phase-1 |
| Cash (via dealers) | Phase-1 |

#### Payment Requirements [MVP]

- Secure payment processing
- Payment confirmation notifications (SMS + Email)
- Receipt generation
- Payment history accessible to user
- Failed payment retry mechanism
- Refund support

### 20.6 Billing Integration [Phase-1]

Requirements:
- Invoice generation
- Payment history
- Auto-renewal
- Upgrade/downgrade flow
- Proration for mid-cycle changes
- Tax calculation and display

---

## 21. Subscription Tiers & Feature Gating

### 21.1 Tier-Based Capabilities [Phase-1]

| Feature | Basic | Standard | Premium | Enterprise |
|---------|-------|----------|---------|------------|
| Polling Interval | 60s | 30s | 10s | 5s |
| Data Retention | 30 days | 90 days | 1 year | Unlimited |
| Users per System | 2 | 5 | 10 | Unlimited |
| AI Optimization | Basic | Standard | Advanced | Custom |
| Reports | Basic | Standard | Advanced | Custom |
| Support | Community | Email | Priority | Dedicated |
| API Access | No | Limited | Full | Full |

*Note: Exact tier definitions to be finalized before launch*

### 21.2 Feature Gating Examples [Phase-1]

| Feature | Gating Rule |
|---------|-------------|
| Telemetry < 60s | Requires Standard+ tier |
| Export to CSV | Requires Standard+ tier |
| Scheduled Reports | Requires Premium+ tier |
| API Access | Requires Premium+ tier |
| Custom Integrations | Requires Enterprise tier |

### 21.3 Centralized Feature Control [Phase-1]

Feature gating enforced consistently across:
- Platform backend (System A)
- Communication backend (System B)
- Frontend UI

### 21.4 Upgrade Prompts [Phase-1]

When user attempts gated feature:
- Clear message explaining limitation
- Show which tier enables feature
- Direct upgrade path
- Never silently fail or degrade

---

## 22. Frontend Requirements

### 22.1 General Requirements [MVP]

- Single codebase for basic and advanced users
- Complexity shown/hidden based on user mode
- Responsive design (mobile-first)
- Progressive Web App (PWA) capable
- Modern browser support

### 22.2 Core UI Components [MVP]

| Component | Description |
|-----------|-------------|
| Dashboard | Overview of all systems, key metrics |
| System View | Single system details, devices |
| Device View | Individual device telemetry, controls |
| Real-time Display | Live updating values |
| Historical Charts | Time-series data visualization |
| Settings | User, system, device configuration |
| Notifications | Alert center, notification history |

### 22.3 Dashboard Requirements [MVP]

Display:
- Total generation (today, month, total)
- Current power flow (solar, grid, battery, load)
- System status (online/offline/fault)
- Key alerts
- Quick actions

### 22.4 Device Management UI [MVP]

- List all devices in system
- Add new device (commissioning flow)
- View device details
- Configure device settings
- Execute commands
- View device alerts

### 22.5 Advanced Features UI [Phase-1]

- Hierarchy editor (for advanced users)
- Scheduler interface
- Billing dashboard
- Report generator
- Export interface

---

## 23. Security Requirements

### 23.1 Transport Security [MVP]

- HTTPS everywhere (TLS 1.2+)
- Secure WebSocket (WSS) for real-time
- Certificate validation enforced
- No mixed content

### 23.2 Authentication Security [MVP]

- Strong password requirements
- Secure password storage (bcrypt/argon2)
- Session management with secure tokens
- Session timeout and renewal
- Multi-device session management
- Optional: Two-factor authentication (Phase-2)

### 23.3 Device Security [MVP]

- Device auth separate from user auth
- Unique credentials per device
- Token expiry and rotation
- Revocation capability
- Secure provisioning process

### 23.4 API Security [MVP]

- Rate limiting per user/IP
- Input validation on all endpoints
- Output encoding
- CORS properly configured
- No sensitive data in URLs

### 23.5 Data Security [MVP]

- Encryption at rest for sensitive data
- No secrets in logs
- Audit logging for sensitive operations
- Secure credential storage
- Regular security reviews

### 23.6 Compliance [Phase-2]

- GDPR compliance
- Data retention policies
- Right to data export
- Right to deletion
- Consent management
- Privacy policy enforcement

---

## 24. Non-Functional Requirements

### 24.1 Performance [MVP]

| Metric | Target |
|--------|--------|
| API response time (p95) | < 200ms |
| Dashboard load time | < 3 seconds |
| Real-time telemetry latency | < 5 seconds |
| Concurrent users | 10,000+ |

### 24.2 Scalability [MVP]

- Support millions of single-device users
- Support thousands of multi-device systems
- Horizontal scaling capability
- Database partitioning strategy
- Efficient telemetry ingestion

### 24.3 Reliability [MVP]

- Graceful degradation on component failure
- Automatic retry and reconnection
- Data durability (no data loss)
- Backup and recovery procedures
- Health monitoring and alerting

### 24.4 Availability [Phase-2]

| Tier | Target Uptime |
|------|---------------|
| Standard | 99.5% |
| Premium | 99.9% |
| Enterprise | 99.95% |

### 24.5 Maintainability [MVP]

- Modular architecture
- Clear separation of concerns
- Comprehensive logging
- Monitoring and observability
- Documentation

---

## 25. Phase-2: Platform Maturity

### 25.1 Mobile Applications [Phase-2]

Requirements:
- Native iOS application
- Native Android application
- Feature parity with web (core features)
- Push notification support
- Offline mode (view cached data)
- Biometric authentication

### 25.2 Data Privacy & Compliance [Phase-2]

Requirements:
- GDPR compliance implementation
- Data retention policy enforcement
- User data export (machine-readable)
- Account deletion with data purge
- Consent management for communications
- Privacy dashboard for users

### 25.3 SLA & Availability [Phase-2]

Requirements:
- Defined uptime guarantees per tier
- Planned maintenance windows
- Incident communication process
- Status page
- Compensation policy for breaches

### 25.4 Support & Customer Service [Phase-2]

Requirements:
- In-app support chat
- Ticket system integration
- Knowledge base / FAQ
- Remote diagnostics tools
- Support tier by subscription

### 25.5 White-Label / Reseller Model [Phase-2]

Requirements:
- Installer/dealer accounts
- Custom branding (logo, colors)
- Dealer dashboard
- Customer management for dealers
- Commission/revenue sharing model
- Branded mobile apps (Enterprise)

### 25.6 Third-Party Integrations [Phase-2]

Requirements:
- Webhook notifications
- Public API with documentation
- OAuth for third-party apps
- Smart home integrations (future)
- Energy trading platforms (future)

---

## 26. Phase-3: Corporate & Enterprise

> **Note:** This section outlines future requirements for corporate/enterprise deployments. Detailed specifications to be developed before Phase-3.

### 26.1 Corporate Account Structure

```
Corporate Account
├── Corporate Admin(s)
├── Sites / Locations
│   ├── Site 1
│   │   ├── Site Manager(s)
│   │   └── Systems
│   ├── Site 2
│   └── Site N
├── Corporate Dashboard
├── Consolidated Reporting
└── Corporate Billing
```

### 26.2 Multi-Site Management

Requirements:
- Single corporate account with multiple sites
- Centralized user management
- Site-level and corporate-level admins
- Cross-site visibility and control
- Site grouping and tagging

### 26.3 Corporate Dashboard

Requirements:
- Aggregated view across all sites
- Key metrics rolled up (generation, savings)
- Site comparison and ranking
- Drill-down to individual sites
- Executive summary view

### 26.4 Corporate Reporting & Analytics

Requirements:
- Cross-site reports
- Consolidated energy reports
- Cost allocation reports
- Performance benchmarking
- Custom report builder
- Automated executive reports

### 26.5 Corporate Billing & Cost Allocation

Requirements:
- Single invoice for all sites
- Cost breakdown by site
- Department/cost center allocation
- Volume discounts
- Custom billing cycles
- Purchase order support

### 26.6 Fleet Management

Requirements:
- Bulk device management
- Mass firmware updates
- Fleet health overview
- Standardized configurations
- Centralized alerting rules

### 26.7 Enterprise Roles & Permissions

Additional roles:
- Corporate Admin (all sites)
- Site Manager (single site)
- Regional Manager (site groups)
- Finance/Billing Admin
- Read-only Executive

### 26.8 Enterprise API Access

Requirements:
- Full API access for integrations
- Higher rate limits
- Dedicated API endpoints
- Custom data feeds
- ERP/BMS integration support

### 26.9 Enterprise Support

Requirements:
- Dedicated account manager
- Custom SLA agreements
- Priority incident response
- On-site support (optional)
- Training and onboarding

### 26.10 Future Corporate Features (Placeholder)

- Energy trading between sites
- Carbon footprint tracking
- Regulatory compliance reporting
- Predictive maintenance
- AI-powered fleet optimization
- Virtual Power Plant (VPP) participation

---

## 27. Out of Scope

The following are explicitly **not** in scope for any current phase:

- Hardware manufacturing workflows
- Physical inventory management
- Business invoicing systems (external to platform)
- Regulatory reporting (Phase-3 placeholder only)
- Third-party energy trading (Phase-3 placeholder only)
- Grid operator integrations
- Utility company integrations

---

## 28. Appendix: Phase Summary Matrix

### Feature by Phase

| Feature | MVP | Phase-1 | Phase-2 | Phase-3 |
|---------|-----|---------|---------|---------|
| **Core Platform** | | | | |
| User Authentication | X | | | |
| Device Authentication | X | | | |
| Telemetry Ingestion | X | | | |
| Real-time Monitoring | X | | | |
| Basic Commands | X | | | |
| Auto Hierarchy | X | | | |
| Basic Subscription | X | | | |
| User Roles (OAVI) | X | | | |
| Installation & Commissioning | X | | | |
| **Ease of Use** | | | | |
| Guided Setup Wizard | X | | | |
| Smart Defaults | X | | | |
| Simple/Advanced Mode | X | | | |
| Offline-First PWA | X | | | |
| **Alerts & Notifications** | | | | |
| Email Alerts | X | | | |
| SMS Alerts | X | | | |
| In-App Notifications | X | | | |
| WhatsApp Alerts | | | X | |
| **Rich Dashboards** | | | | |
| Power Flow Animation | X | | | |
| Customizable Widgets | X | | | |
| Comparison Views | X | | | |
| Goal Tracking | X | | | |
| Environmental Impact | X | | | |
| **AI Features** | | | | |
| Battery Optimization | X | | | |
| Anomaly Detection | X | | | |
| Generation Forecasting | X | | | |
| Consumption Patterns | X | | | |
| Personalized Insights | X | | | |
| Predictive Maintenance | | X | | |
| Natural Language Queries | | | X | |
| **Billing & Simulation** | | | | |
| Energy Billing | X | | | |
| What-If Scenarios | X | | | |
| ROI Calculator | X | | | |
| Savings Tracker | X | | | |
| Bill Reconciliation | X | | | |
| **Local Market (Pakistan)** | | | | |
| Load Shedding Tracking | X | | | |
| Outage Reports | X | | | |
| Net Metering Support | X | | | |
| DISCO Tariffs (Pre-loaded) | X | | | |
| JazzCash/EasyPaisa | X | | | |
| Urdu Language | | | X | |
| **Subscription & Payments** | | | | |
| Basic Subscription | X | | | |
| Mobile Wallet Payments | X | | | |
| Subscription Tiers | | X | | |
| Bank/Card Payments | | X | | |
| **Reporting & Export** | | | | |
| Standard Reports | | X | | |
| PDF/CSV/Excel Export | | X | | |
| Scheduled Reports | | X | | |
| **Device Management** | | | | |
| OTA Updates | | X | | |
| Device Replacement | | X | | |
| Advanced Hierarchy | | X | | |
| **Phase-2 Features** | | | | |
| Mobile Apps | | | X | |
| GDPR Compliance | | | X | |
| SLA Guarantees | | | X | |
| Support Integration | | | X | |
| White-Label | | | X | |
| Webhooks/API | | | X | |
| **Phase-3 Features** | | | | |
| Multi-Site Corporate | | | | X |
| Corporate Dashboard | | | | X |
| Fleet Management | | | | X |
| Enterprise Roles | | | | X |
| Enterprise API | | | | X |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | - | Initial requirements |
| 2.0 | - | Added phases, user management, alerts, commissioning, reporting, lifecycle, corporate features |
| 3.0 | - | Added differentiators: Ease of Use, Rich Dashboards, AI Features, Billing Simulation, Load Shedding, Pakistan local market features, Payment methods |

---

**End of Requirements Document**
