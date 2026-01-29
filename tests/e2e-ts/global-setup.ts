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

  try {
    // Navigate to login page
    await page.goto(`${baseURL}/auth`, { waitUntil: 'domcontentloaded' });

    // Wait for login form to be visible
    await page.waitForSelector('input[type="email"]', { timeout: 10000 });

    // Fill credentials
    const emailInput = page.locator('input[type="email"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    await emailInput.fill(credentials.email);
    await passwordInput.fill(credentials.password);

    // Submit login
    const submitButton = page.locator('button[type="submit"]').first();
    await submitButton.click();

    // Wait for successful login - either dashboard URL or token in localStorage
    try {
      await page.waitForURL('**/dashboard', { timeout: 15000 });
    } catch (urlError) {
      // If URL doesn't change, check for token in localStorage
      await page.waitForTimeout(3000);
    }

    // Verify token exists in localStorage
    const token = await page.evaluate(() => localStorage.getItem('token'));

    if (!token) {
      throw new Error(`No auth token found for ${role}`);
    }

    // Save authentication state
    await page.context().storageState({ path: credentials.storageStatePath });

    console.log(`   ✓ ${role} authentication saved to ${path.basename(credentials.storageStatePath)}`);
  } catch (error) {
    console.error(`   ✗ ${role} authentication failed:`, error instanceof Error ? error.message : error);
    throw error;
  }
}

export default globalSetup;
