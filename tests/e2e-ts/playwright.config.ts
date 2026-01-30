import { defineConfig, devices } from '@playwright/test';
import * as path from 'path';

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
require('dotenv').config({ path: path.resolve(__dirname, '.env.test') });

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  /**
   * Test directory
   */
  testDir: './tests',

  /**
   * Test match patterns
   */
  testMatch: '**/*.spec.ts',

  /**
   * Maximum time one test can run for (30 seconds)
   */
  timeout: 30 * 1000,

  /**
   * Run tests in files in parallel
   */
  fullyParallel: true,

  /**
   * Fail the build on CI if you accidentally left test.only in the source code.
   */
  forbidOnly: !!process.env.CI,

  /**
   * Retry on CI only
   * - CI: 2 retries (flaky network, race conditions)
   * - Local: 0 retries (faster feedback, encourages fixing flaky tests)
   */
  retries: process.env.CI ? 2 : 0,

  /**
   * Number of parallel workers
   * - CI: 2 workers (resource-constrained)
   * - Local: 50% of CPU cores
   */
  workers: process.env.CI ? 2 : undefined,

  /**
   * Reporter to use
   * - CI: JSON reporter + HTML reporter
   * - Local: List reporter + HTML reporter
   */
  reporter: [
    ['list'],
    ['html', {
      outputFolder: 'test-results/reports',
      open: process.env.CI ? 'never' : 'on-failure',
    }],
    ['json', {
      outputFile: 'test-results/results.json'
    }],
    // Custom reporters (uncomment when ready)
    // ['./reporters/slack-reporter.ts'],
    // ['./reporters/jira-reporter.ts'],
  ],

  /**
   * Global timeout for the entire test run (1 hour)
   */
  globalTimeout: 60 * 60 * 1000,

  /**
   * Expect timeout for assertions (5 seconds)
   */
  expect: {
    timeout: 5 * 1000,
    toHaveScreenshot: {
      // Slightly less strict screenshot comparison
      maxDiffPixelRatio: 0.05,
    },
  },

  /**
   * Shared settings for all the projects below
   */
  use: {
    /**
     * Base URL to use in actions like `await page.goto('/')`
     */
    baseURL: process.env.BASE_URL || 'http://localhost:8081',

    /**
     * Collect trace when retrying the failed test
     */
    trace: process.env.CI ? 'on-first-retry' : 'retain-on-failure',

    /**
     * Screenshot on failure
     */
    screenshot: 'only-on-failure',

    /**
     * Video on failure
     */
    video: process.env.CI ? 'retain-on-failure' : 'off',

    /**
     * Maximum time each action (click, fill, etc.) can take
     */
    actionTimeout: 10 * 1000,

    /**
     * Navigation timeout (page loads, redirects)
     */
    navigationTimeout: 15 * 1000,

    /**
     * Ignore HTTPS errors (useful for local development with self-signed certs)
     */
    ignoreHTTPSErrors: true,

    /**
     * Permissions
     */
    permissions: ['clipboard-read', 'clipboard-write'],

    /**
     * Geolocation for weather features
     */
    geolocation: { latitude: 31.5204, longitude: 74.3587 }, // Lahore, Pakistan

    /**
     * Locale
     */
    locale: 'en-US',

    /**
     * Timezone
     */
    timezoneId: 'Asia/Karachi',

    /**
     * Extra HTTP headers
     */
    extraHTTPHeaders: {
      'Accept-Language': 'en-US,en;q=0.9',
    },

    /**
     * Context options
     */
    contextOptions: {
      reducedMotion: 'no-preference',
      strictSelectors: true, // Enforce strict selector syntax
    },
  },

  /**
   * Configure projects for major browsers
   */
  projects: [
    /**
     * Setup project for authentication and global setup
     */
    {
      name: 'setup',
      testMatch: /global-setup\.ts/,
    },

    /**
     * Desktop Chrome
     */
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 720 },
        storageState: 'test-results/.auth/owner.json',
      },
      dependencies: ['setup'],
    },

    /**
     * Desktop Firefox
     */
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        viewport: { width: 1280, height: 720 },
      },
      dependencies: ['setup'],
    },

    /**
     * Desktop Safari (WebKit)
     */
    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
        viewport: { width: 1280, height: 720 },
      },
      dependencies: ['setup'],
    },

    /**
     * Mobile Chrome
     */
    {
      name: 'mobile-chrome',
      use: {
        ...devices['Pixel 5'],
      },
      dependencies: ['setup'],
    },

    /**
     * Mobile Safari
     */
    {
      name: 'mobile-safari',
      use: {
        ...devices['iPhone 12'],
      },
      dependencies: ['setup'],
    },

    /**
     * Tablet
     */
    {
      name: 'tablet',
      use: {
        ...devices['iPad Pro'],
      },
      dependencies: ['setup'],
    },

    /**
     * Branded browser tests (uncomment if needed)
     */
    // {
    //   name: 'Microsoft Edge',
    //   use: { ...devices['Desktop Edge'], channel: 'msedge' },
    //   dependencies: ['setup'],
    // },
    // {
    //   name: 'Google Chrome',
    //   use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    //   dependencies: ['setup'],
    // },
  ],

  /**
   * Global setup script
   * Runs once before all tests
   */
  globalSetup: require.resolve('./global-setup'),

  /**
   * Global teardown script
   * Runs once after all tests
   */
  globalTeardown: require.resolve('./global-teardown'),

  /**
   * Output directory for test artifacts
   */
  outputDir: 'test-results/artifacts',

  /**
   * Preserve output from previous test runs
   */
  preserveOutput: 'failures-only',

  /**
   * Update snapshots on failures
   */
  updateSnapshots: process.env.UPDATE_SNAPSHOTS === 'true' ? 'all' : 'missing',

  /**
   * Maximum failures before stopping
   * Useful for failing fast in CI
   */
  maxFailures: process.env.CI ? 10 : undefined,

  /**
   * Shard tests for parallel execution
   * Example: npx playwright test --shard=1/4
   */
  // shard: process.env.CI ? { current: 1, total: 4 } : undefined,

  /**
   * Grep patterns for test filtering
   * Example: npx playwright test --grep @smoke
   */
  // grep: /@smoke/,
  // grepInvert: /@skip/,

  /**
   * Web server configuration
   * Automatically start frontend server before tests
   * Disabled for remote testing
   */
  // webServer: process.env.CI ? {
  //   command: 'npm run dev',
  //   url: 'http://localhost:8081',
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 120 * 1000, // 2 minutes to start server
  //   stdout: 'pipe',
  //   stderr: 'pipe',
  // } : undefined,

  /**
   * Metadata for reporters
   */
  metadata: {
    testEnvironment: process.env.TEST_ENV || 'local',
    buildNumber: process.env.BUILD_NUMBER,
    branch: process.env.GIT_BRANCH,
    commit: process.env.GIT_COMMIT,
  },
});
