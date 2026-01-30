import { chromium, FullConfig } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config({ path: '.env.test' });

interface AuthCredentials {
  email: string;
  password: string;
  storageStatePath: string;
}

async function globalSetup(config: FullConfig) {
  console.log('\n🚀 Starting global setup...\n');

  const baseURL = process.env.BASE_URL || 'http://localhost:8081';

  // Ensure auth directory exists
  const authDir = path.join(__dirname, 'test-results', '.auth');
  if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
  }

  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Setup authentication for different roles
  const roles: Record<string, AuthCredentials> = {
    owner: {
      email: process.env.OWNER_EMAIL || 'owner@solarhub.com',
      password: process.env.OWNER_PASSWORD || 'Owner123!@#',
      storageStatePath: path.join(authDir, 'owner.json'),
    },
    admin: {
      email: process.env.ADMIN_EMAIL || 'admin@solarhub.com',
      password: process.env.ADMIN_PASSWORD || 'Admin123!@#',
      storageStatePath: path.join(authDir, 'admin.json'),
    },
    viewer: {
      email: process.env.VIEWER_EMAIL || 'viewer@solarhub.com',
      password: process.env.VIEWER_PASSWORD || 'Viewer123!@#',
      storageStatePath: path.join(authDir, 'viewer.json'),
    },
    installer: {
      email: process.env.INSTALLER_EMAIL || 'installer@solarhub.com',
      password: process.env.INSTALLER_PASSWORD || 'Installer123!@#',
      storageStatePath: path.join(authDir, 'installer.json'),
    },
  };

  // Authenticate for each role
  for (const [role, credentials] of Object.entries(roles)) {
    try {
      await setupAuthState(page, role, credentials, baseURL);
    } catch (error) {
      console.error(`❌ Failed to setup ${role} authentication:`, error);
      // Continue with other roles even if one fails
    }
  }

  await browser.close();

  console.log('\n✅ Global setup completed\n');
}

async function setupAuthState(
  page: any,
  role: string,
  credentials: AuthCredentials,
  baseURL: string
) {
  console.log(`🔑 Setting up ${role} authentication...`);
  console.log(`   Email: ${credentials.email}`);

  try {
    // Navigate to login page with extended timeout
    console.log(`   → Navigating to ${baseURL}/auth...`);
    await page.goto(`${baseURL}/auth`, {
      waitUntil: 'networkidle',
      timeout: 30000
    });

    // Wait for page to be fully loaded
    await page.waitForTimeout(2000);

    // Check if already redirected to dashboard (already logged in)
    if (page.url().includes('/dashboard') || page.url() === `${baseURL}/`) {
      console.log(`   ⚠ Already authenticated, logging out first...`);
      // Logout by clearing storage
      await page.evaluate(() => {
        localStorage.clear();
        sessionStorage.clear();
      });
      await page.goto(`${baseURL}/auth`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(2000);
    }

    // Wait for login form to be visible
    console.log(`   → Waiting for login form...`);
    await page.waitForSelector('input[type="email"]', {
      timeout: 15000,
      state: 'visible'
    });

    // Fill credentials with delays to prevent re-renders
    console.log(`   → Filling credentials...`);
    const emailInput = page.locator('input[type="email"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    await emailInput.clear();
    await emailInput.fill(credentials.email);
    await page.waitForTimeout(500); // Wait for validation

    await passwordInput.clear();
    await passwordInput.fill(credentials.password);
    await page.waitForTimeout(500); // Wait for validation

    // Find and click the login button
    console.log(`   → Submitting login form...`);
    const submitButton = page.locator('button[type="submit"]').first();

    // Wait for button to be enabled
    await page.waitForTimeout(500);

    // Click submit with force to handle potential detachment
    await submitButton.click({ force: true });

    // Wait for navigation or token
    console.log(`   → Waiting for authentication...`);
    let authenticated = false;
    let attempts = 0;
    const maxAttempts = 30; // 30 seconds total

    while (!authenticated && attempts < maxAttempts) {
      await page.waitForTimeout(1000);
      attempts++;

      // Check if redirected to dashboard
      const currentUrl = page.url();
      if (currentUrl.includes('/dashboard') || currentUrl === `${baseURL}/` || currentUrl === `${baseURL}`) {
        console.log(`   → Redirected to: ${currentUrl}`);
        authenticated = true;
        break;
      }

      // Check if token exists
      const token = await page.evaluate(() => localStorage.getItem('solar_hub_access_token'));
      if (token) {
        console.log(`   → Token found in localStorage`);
        authenticated = true;
        break;
      }

      // Check for critical error messages (ignore dashboard preference errors)
      const errorVisible = await page.locator('text=/invalid credentials|authentication failed|login failed/i').isVisible({ timeout: 100 }).catch(() => false);
      if (errorVisible) {
        const errorText = await page.locator('text=/invalid credentials|authentication failed|login failed/i').first().textContent();
        throw new Error(`Login failed: ${errorText}`);
      }

      // Dismiss any non-critical toast notifications (like dashboard preference errors)
      const toastDismiss = page.locator('[aria-label="Close"]').or(page.locator('button:has-text("×")')).first();
      if (await toastDismiss.isVisible({ timeout: 100 }).catch(() => false)) {
        await toastDismiss.click({ timeout: 1000 }).catch(() => {});
      }
    }

    if (!authenticated) {
      // Take screenshot for debugging
      await page.screenshot({ path: path.join(__dirname, 'test-results', `.auth-failure-${role}.png`) });
      throw new Error(`Authentication timeout after ${maxAttempts} seconds`);
    }

    // Verify token exists in localStorage
    const token = await page.evaluate(() => localStorage.getItem('solar_hub_access_token'));
    if (!token) {
      throw new Error(`No auth token found for ${role} after successful login`);
    }

    console.log(`   → Token verified: ${token.substring(0, 20)}...`);

    // Save authentication state
    await page.context().storageState({ path: credentials.storageStatePath });

    console.log(`   ✓ ${role} authentication saved to ${path.basename(credentials.storageStatePath)}`);
  } catch (error) {
    // Enhanced error logging
    console.error(`   ✗ ${role} authentication failed:`);
    console.error(`      URL: ${page.url()}`);
    console.error(`      Error: ${error instanceof Error ? error.message : error}`);

    // Take screenshot for debugging
    try {
      await page.screenshot({
        path: path.join(__dirname, 'test-results', `.auth-error-${role}.png`),
        fullPage: true
      });
      console.error(`      Screenshot saved: test-results/.auth-error-${role}.png`);
    } catch (screenshotError) {
      console.error(`      Could not take screenshot: ${screenshotError}`);
    }

    throw error;
  }
}

export default globalSetup;
