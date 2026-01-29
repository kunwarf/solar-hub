# Playwright TypeScript E2E Test Folder Structure

```
tests/e2e-ts/
├── playwright.config.ts              # Main Playwright configuration
├── package.json                       # Test dependencies
├── tsconfig.json                      # TypeScript configuration
├── .env.test                          # Test environment variables
├── .gitignore                         # Git ignore for test artifacts
│
├── tests/                             # Test suites
│   ├── auth/
│   │   ├── login.spec.ts             # Login flow tests
│   │   ├── registration.spec.ts      # User registration tests
│   │   ├── password-reset.spec.ts    # Password reset flow
│   │   └── session.spec.ts           # Session management tests
│   │
│   ├── onboarding/
│   │   ├── setup-wizard.spec.ts      # Complete wizard flow
│   │   ├── device-claiming.spec.ts   # Device pairing during signup
│   │   └── profile-setup.spec.ts     # User profile configuration
│   │
│   ├── dashboard/
│   │   ├── power-flow.spec.ts        # Power flow diagram tests
│   │   ├── real-time-data.spec.ts    # Live telemetry updates
│   │   ├── widgets.spec.ts           # Dashboard widget tests
│   │   ├── customization.spec.ts     # Layout customization
│   │   └── responsive.spec.ts        # Responsive design tests
│   │
│   ├── devices/
│   │   ├── device-list.spec.ts       # Device inventory
│   │   ├── device-detail.spec.ts     # Individual device view
│   │   ├── device-claiming.spec.ts   # Claim/release devices
│   │   ├── device-config.spec.ts     # Device configuration
│   │   └── multi-device.spec.ts      # Multiple devices scenarios
│   │
│   ├── billing/
│   │   ├── billing-cycles.spec.ts    # Billing cycle generation
│   │   ├── net-metering.spec.ts      # Net metering calculations
│   │   ├── tariff-config.spec.ts     # Tariff configuration
│   │   ├── billing-history.spec.ts   # Past billing cycles
│   │   └── export-credits.spec.ts    # Export credit tracking
│   │
│   ├── analytics/
│   │   ├── energy-charts.spec.ts     # Production/consumption charts
│   │   ├── period-comparison.spec.ts # Time period comparisons
│   │   ├── battery-performance.spec.ts # Battery analytics
│   │   └── reports.spec.ts           # Report generation
│   │
│   ├── alerts/
│   │   ├── alert-rules.spec.ts       # Alert rule configuration
│   │   ├── alert-triggering.spec.ts  # Alert firing logic
│   │   ├── notifications.spec.ts     # Alert notifications
│   │   └── alert-history.spec.ts     # Alert log
│   │
│   ├── outages/
│   │   ├── grid-status.spec.ts       # Grid online/offline detection
│   │   ├── outage-tracking.spec.ts   # Outage duration logging
│   │   ├── battery-backup.spec.ts    # Backup time estimation
│   │   └── outage-history.spec.ts    # Historical outages
│   │
│   ├── admin/
│   │   ├── user-management.spec.ts   # User CRUD operations
│   │   ├── roles.spec.ts             # Role assignment
│   │   ├── invitations.spec.ts       # User invitations
│   │   └── organization.spec.ts      # Organization management
│   │
│   ├── settings/
│   │   ├── profile.spec.ts           # User profile settings
│   │   ├── notifications.spec.ts     # Notification preferences
│   │   ├── site-config.spec.ts       # Site configuration
│   │   └── subscription.spec.ts      # Subscription management
│   │
│   └── integration/
│       ├── device-registration.spec.ts  # ESP32 device registration
│       ├── cross-system.spec.ts         # System A ↔ System B
│       ├── redis-cache.spec.ts          # Redis integration
│       └── payment-gateway.spec.ts      # Payment processing
│
├── pages/                             # Page Object Models
│   ├── base/
│   │   ├── BasePage.ts               # Base page class
│   │   ├── AuthenticatedPage.ts      # Authenticated page base
│   │   └── Component.ts              # Reusable component base
│   │
│   ├── auth/
│   │   ├── LoginPage.ts              # Login page object
│   │   ├── RegistrationPage.ts       # Registration page object
│   │   └── PasswordResetPage.ts      # Password reset page
│   │
│   ├── dashboard/
│   │   ├── DashboardPage.ts          # Main dashboard page
│   │   ├── PowerFlowComponent.ts     # Power flow widget
│   │   ├── StatsComponent.ts         # Stats cards widget
│   │   ├── EnergyChartComponent.ts   # Energy chart widget
│   │   └── WidgetPickerComponent.ts  # Widget customization
│   │
│   ├── devices/
│   │   ├── DevicesPage.ts            # Device list page
│   │   ├── DeviceDetailPage.ts       # Device detail page
│   │   ├── ClaimDevicePage.ts        # Device claiming flow
│   │   └── DeviceConfigPage.ts       # Device configuration
│   │
│   ├── billing/
│   │   ├── BillingPage.ts            # Billing overview page
│   │   ├── TariffSettingsPage.ts     # Tariff configuration
│   │   └── BillingHistoryPage.ts     # Billing history
│   │
│   ├── analytics/
│   │   ├── AnalyticsPage.ts          # Analytics dashboard
│   │   └── ReportsPage.ts            # Report generation
│   │
│   ├── alerts/
│   │   ├── AlertsPage.ts             # Alert center
│   │   └── AlertRulesPage.ts         # Alert rule configuration
│   │
│   ├── outages/
│   │   ├── OutagesPage.ts            # Outage tracking page
│   │   └── GridStatusComponent.ts    # Grid status widget
│   │
│   ├── admin/
│   │   ├── UserManagementPage.ts     # User admin page
│   │   ├── InvitationsPage.ts        # User invitations
│   │   └── OrganizationPage.ts       # Organization settings
│   │
│   └── settings/
│       ├── SettingsPage.ts           # Settings hub
│       ├── ProfilePage.ts            # User profile
│       └── NotificationsPage.ts      # Notification settings
│
├── fixtures/                          # Test fixtures and setup
│   ├── auth.fixture.ts               # Authentication fixtures
│   ├── user.fixture.ts               # User data fixtures
│   ├── device.fixture.ts             # Device data fixtures
│   ├── telemetry.fixture.ts          # Telemetry data fixtures
│   ├── billing.fixture.ts            # Billing data fixtures
│   └── test-setup.ts                 # Global test setup
│
├── utils/                             # Utility functions
│   ├── api/
│   │   ├── auth.api.ts               # Auth API helpers
│   │   ├── devices.api.ts            # Device API helpers
│   │   ├── telemetry.api.ts          # Telemetry API helpers
│   │   └── billing.api.ts            # Billing API helpers
│   │
│   ├── helpers/
│   │   ├── wait.ts                   # Custom wait utilities
│   │   ├── assertions.ts             # Custom assertions
│   │   ├── data-generator.ts         # Test data generation
│   │   ├── date.ts                   # Date manipulation
│   │   └── selectors.ts              # Selector builders
│   │
│   ├── database/
│   │   ├── db-client.ts              # Database connection
│   │   ├── seed.ts                   # Database seeding
│   │   └── cleanup.ts                # Database cleanup
│   │
│   └── mock/
│       ├── device-simulator.ts       # Mock device telemetry
│       ├── mqtt-mock.ts              # Mock MQTT broker
│       └── api-mocks.ts              # Mock API responses
│
├── data/                              # Test data files
│   ├── users.json                    # User test data
│   ├── devices.json                  # Device test data
│   ├── tariffs.json                  # Tariff configurations
│   ├── disco-providers.json          # DISCO providers
│   └── telemetry-patterns.json       # Telemetry patterns
│
├── reporters/                         # Custom reporters
│   ├── html-reporter.ts              # Enhanced HTML report
│   ├── slack-reporter.ts             # Slack notification reporter
│   ├── jira-reporter.ts              # JIRA integration reporter
│   └── coverage-reporter.ts          # Test coverage reporter
│
├── types/                             # TypeScript type definitions
│   ├── test.types.ts                 # Test-specific types
│   ├── api.types.ts                  # API response types
│   ├── user.types.ts                 # User data types
│   └── device.types.ts               # Device data types
│
├── global-setup.ts                    # Global setup before all tests
├── global-teardown.ts                 # Global teardown after all tests
│
└── test-results/                      # Test execution artifacts
    ├── screenshots/                   # Failure screenshots
    ├── videos/                        # Test execution videos
    ├── traces/                        # Playwright traces
    ├── reports/                       # HTML reports
    └── logs/                          # Test execution logs
```

## File Naming Conventions

### Test Files
- **Pattern:** `<feature>.spec.ts`
- **Examples:**
  - `login.spec.ts`
  - `device-claiming.spec.ts`
  - `billing-cycles.spec.ts`

### Page Object Files
- **Pattern:** `<PageName>Page.ts` or `<ComponentName>Component.ts`
- **Examples:**
  - `LoginPage.ts`
  - `DashboardPage.ts`
  - `PowerFlowComponent.ts`

### Fixture Files
- **Pattern:** `<feature>.fixture.ts`
- **Examples:**
  - `auth.fixture.ts`
  - `user.fixture.ts`

### Utility Files
- **Pattern:** `<functionality>.ts`
- **Examples:**
  - `wait.ts`
  - `data-generator.ts`

## Import Path Examples

```typescript
// Page Objects
import { LoginPage } from '@/pages/auth/LoginPage';
import { DashboardPage } from '@/pages/dashboard/DashboardPage';

// Fixtures
import { authenticatedUser } from '@/fixtures/auth.fixture';
import { deviceWithTelemetry } from '@/fixtures/device.fixture';

// Utilities
import { waitForTelemetry } from '@/utils/helpers/wait';
import { generateUniqueEmail } from '@/utils/helpers/data-generator';

// API Helpers
import { loginViaAPI } from '@/utils/api/auth.api';
import { seedTelemetryData } from '@/utils/api/telemetry.api';

// Types
import { User, UserRole } from '@/types/user.types';
import { Device, DeviceType } from '@/types/device.types';
```

## TypeScript Path Aliases (tsconfig.json)

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./"],
      "@pages/*": ["./pages/*"],
      "@tests/*": ["./tests/*"],
      "@fixtures/*": ["./fixtures/*"],
      "@utils/*": ["./utils/*"],
      "@data/*": ["./data/*"],
      "@types/*": ["./types/*"]
    }
  }
}
```

## Module Organization Principles

1. **Single Responsibility:** Each file has one clear purpose
2. **Reusability:** Common logic in utilities, page objects reusable
3. **Discoverability:** Intuitive folder structure, clear naming
4. **Maintainability:** Easy to find and update test code
5. **Scalability:** Structure supports 200+ test files

## Migration from Python

When migrating existing Python tests:
- `tests/e2e/test_auth.py` → `tests/e2e-ts/tests/auth/login.spec.ts`
- `tests/e2e/conftest.py` fixtures → `fixtures/*.fixture.ts`
- Helper functions → `utils/helpers/*.ts`
- Page object patterns → `pages/*/*.ts`
