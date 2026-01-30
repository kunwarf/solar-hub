import { chromium } from '@playwright/test';

async function debugLogin() {
  const browser = await chromium.launch({ headless: false, slowMo: 1000 });
  const page = await browser.newPage();

  try {
    console.log('Navigating to login page...');
    await page.goto('http://182.180.150.107:8050/auth', { waitUntil: 'domcontentloaded' });

    console.log('Page loaded, waiting 2 seconds...');
    await page.waitForTimeout(2000);

    console.log('Taking screenshot of login page...');
    await page.screenshot({ path: 'login-page.png' });

    console.log('Looking for email input...');
    const emailInput = page.locator('input[type="email"]').first();
    await emailInput.waitFor({ timeout: 5000 });

    console.log('Filling email...');
    await emailInput.fill('kunwar.faisal@gmail.com');
    await page.waitForTimeout(1000);

    console.log('Looking for password input...');
    const passwordInput = page.locator('input[type="password"]').first();
    await passwordInput.fill('Test@123');
    await page.waitForTimeout(1000);

    console.log('Taking screenshot before click...');
    await page.screenshot({ path: 'before-click.png' });

    console.log('Looking for submit button...');
    const submitButton = page.locator('button[type="submit"]').first();
    await submitButton.waitFor({ timeout: 5000 });

    console.log('Clicking submit button...');
    await submitButton.click({ force: true });

    console.log('Waiting for navigation or response...');
    await page.waitForTimeout(5000);

    console.log('Current URL:', page.url());

    console.log('Taking screenshot after click...');
    await page.screenshot({ path: 'after-click.png' });

    console.log('Checking localStorage...');
    const token = await page.evaluate(() => {
      const allItems = { ...localStorage };
      console.log('LocalStorage contents:', allItems);
      return {
        token: localStorage.getItem('token'),
        authToken: localStorage.getItem('authToken'),
        accessToken: localStorage.getItem('accessToken'),
        allKeys: Object.keys(localStorage),
        allItems
      };
    });
    console.log('Token info:', token);

    console.log('Checking cookies...');
    const cookies = await page.context().cookies();
    console.log('Cookies:', cookies);

    console.log('Checking sessionStorage...');
    const sessionData = await page.evaluate(() => ({
      allItems: { ...sessionStorage }
    }));
    console.log('SessionStorage:', sessionData);

    await page.waitForTimeout(5000);

  } catch (error) {
    console.error('Error:', error);
    await page.screenshot({ path: 'error.png' });
  }

  await browser.close();
}

debugLogin();
