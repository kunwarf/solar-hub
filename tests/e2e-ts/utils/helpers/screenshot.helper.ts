import { Page } from '@playwright/test';
import path from 'path';
import fs from 'fs';

/**
 * Screenshot Helper Utilities
 * Capture and manage screenshots in tests
 */

/**
 * Take full page screenshot
 */
export async function takeFullPageScreenshot(
  page: Page,
  name: string,
  dir: string = 'screenshots'
): Promise<string> {
  const screenshotDir = path.join(process.cwd(), dir);

  // Create directory if it doesn't exist
  if (!fs.existsSync(screenshotDir)) {
    fs.mkdirSync(screenshotDir, { recursive: true });
  }

  const timestamp = Date.now();
  const filename = `${name}_${timestamp}.png`;
  const filepath = path.join(screenshotDir, filename);

  await page.screenshot({
    path: filepath,
    fullPage: true,
  });

  return filepath;
}

/**
 * Take element screenshot
 */
export async function takeElementScreenshot(
  page: Page,
  selector: string,
  name: string,
  dir: string = 'screenshots'
): Promise<string> {
  const screenshotDir = path.join(process.cwd(), dir);

  if (!fs.existsSync(screenshotDir)) {
    fs.mkdirSync(screenshotDir, { recursive: true });
  }

  const timestamp = Date.now();
  const filename = `${name}_${timestamp}.png`;
  const filepath = path.join(screenshotDir, filename);

  const element = await page.locator(selector);
  await element.screenshot({ path: filepath });

  return filepath;
}

/**
 * Take screenshot on test failure
 */
export async function screenshotOnFailure(
  page: Page,
  testName: string
): Promise<string | null> {
  try {
    return await takeFullPageScreenshot(page, `failure_${testName}`, 'screenshots/failures');
  } catch (error) {
    console.error('Failed to take screenshot:', error);
    return null;
  }
}

/**
 * Compare screenshots (basic)
 */
export async function compareScreenshot(
  page: Page,
  baselinePath: string,
  name: string
): Promise<boolean> {
  const screenshot = await page.screenshot();

  // In a real implementation, you would use a library like pixelmatch
  // This is a placeholder
  console.log(`Would compare screenshot ${name} with baseline at ${baselinePath}`);

  return true;
}

/**
 * Capture video of test
 */
export async function captureVideo(
  page: Page,
  testName: string
): Promise<string | null> {
  const videoPath = await page.video()?.path();

  if (videoPath) {
    console.log(`Video captured for ${testName}: ${videoPath}`);
  }

  return videoPath || null;
}

/**
 * Take screenshot with timestamp overlay
 */
export async function takeTimestampedScreenshot(
  page: Page,
  name: string
): Promise<string> {
  const timestamp = new Date().toISOString();

  // Add timestamp to page
  await page.evaluate((ts) => {
    const div = document.createElement('div');
    div.textContent = ts;
    div.style.position = 'fixed';
    div.style.top = '10px';
    div.style.right = '10px';
    div.style.background = 'rgba(0,0,0,0.7)';
    div.style.color = 'white';
    div.style.padding = '5px 10px';
    div.style.borderRadius = '4px';
    div.style.zIndex = '999999';
    div.style.fontSize = '12px';
    div.id = 'playwright-timestamp';
    document.body.appendChild(div);
  }, timestamp);

  const filepath = await takeFullPageScreenshot(page, name);

  // Remove timestamp
  await page.evaluate(() => {
    document.getElementById('playwright-timestamp')?.remove();
  });

  return filepath;
}
