import { defineConfig, devices } from '@playwright/test';
import * as path from 'path';

/**
 * Regression Test Suite Configuration
 *
 * This configuration is optimized for comprehensive regression testing
 * against local development environment.
 *
 * Usage:
 *   npm run test:regression:local    - Run full regression suite
 *   npm run test:regression:smoke    - Run smoke tests only
 *   npm run test:regression:critical - Run critical tests only
 */

// Load local environment variables
require('dotenv').config({ path: path.resolve(__dirname, '.env.local') });

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',

  // Regression suite runs slower with more thorough checks
  timeout: 60 * 1000, // 60 seconds per test

  // Run tests in parallel for faster execution
  fullyParallel: true,

  // No retries for regression - we want to catch all issues
  retries: 0,

  // Use more workers for faster local execution
  workers: parseInt(process.env.WORKERS || '4'),

  // Comprehensive reporting for regression
  reporter: [
    ['list', { printSteps: true }],
    ['html', {
      outputFolder: 'test-results/regression-report',
      open: 'never',
    }],
    ['json', {
      outputFile: 'test-results/regression-results.json'
    }],
    ['junit', {
      outputFile: 'test-results/regression-junit.xml'
    }],
  ],

  globalTimeout: 2 * 60 * 60 * 1000, // 2 hours for full suite

  expect: {
    timeout: 10 * 1000, // 10 seconds for assertions
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.05,
      animations: 'disabled',
    },
  },

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8081',

    // Enable trace for all tests in regression
    trace: 'retain-on-failure',

    // Always capture screenshots and videos for regression
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',

    actionTimeout: 15 * 1000,
    navigationTimeout: 30 * 1000,

    ignoreHTTPSErrors: true,
    permissions: ['clipboard-read', 'clipboard-write', 'notifications'],
    geolocation: { latitude: 31.5204, longitude: 74.3587 },
    locale: 'en-US',
    timezoneId: 'Asia/Karachi',

    extraHTTPHeaders: {
      'Accept-Language': 'en-US,en;q=0.9',
    },

    contextOptions: {
      reducedMotion: 'no-preference',
      strictSelectors: true,
    },
  },

  projects: [
    // Setup authentication
    {
      name: 'setup',
      testMatch: /global-setup\.ts/,
    },

    // Primary regression browser: Chromium
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1920, height: 1080 },
        storageState: 'test-results/.auth/owner.json',
      },
      dependencies: ['setup'],
    },

    // Secondary browsers (optional, can be enabled for full coverage)
    // {
    //   name: 'firefox',
    //   use: {
    //     ...devices['Desktop Firefox'],
    //     viewport: { width: 1920, height: 1080 },
    //     storageState: 'test-results/.auth/owner.json',
    //   },
    //   dependencies: ['setup'],
    // },
    // {
    //   name: 'webkit',
    //   use: {
    //     ...devices['Desktop Safari'],
    //     viewport: { width: 1920, height: 1080 },
    //     storageState: 'test-results/.auth/owner.json',
    //   },
    //   dependencies: ['setup'],
    // },
  ],

  globalSetup: require.resolve('./global-setup'),
  globalTeardown: require.resolve('./global-teardown'),

  outputDir: 'test-results/regression-artifacts',
  preserveOutput: 'always', // Keep all artifacts for regression analysis

  updateSnapshots: 'missing',

  // Fail fast disabled - run all tests to get complete picture
  maxFailures: undefined,

  metadata: {
    testEnvironment: 'local',
    suiteType: 'regression',
    timestamp: new Date().toISOString(),
  },
});
