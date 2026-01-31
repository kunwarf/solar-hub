import { test, expect } from '@/fixtures/auth.fixture';

test('debug settings page API calls', async ({ authenticatedPage }) => {
  const deviceId = '669a0686-f574-445d-93cf-7ff1bc078b29';

  // Listen to all API requests/responses
  const apiCalls: Array<{url: string, status: number, response: any}> = [];

  authenticatedPage.on('response', async (response) => {
    const url = response.url();
    if (url.includes('/api/v1/devices/') && url.includes(deviceId)) {
      try {
        const data = await response.json();
        apiCalls.push({
          url: url.replace('http://182.180.150.107:8000', ''),
          status: response.status(),
          response: data
        });
        console.log(`\n[API] ${response.status()} ${url.replace('http://182.180.150.107:8000', '')}`);
        console.log(`[DATA]`, JSON.stringify(data, null, 2).substring(0, 500));
      } catch (e) {
        // Not JSON
      }
    }
  });

  // Navigate to settings page
  console.log(`\n=== Navigating to settings page ===\n`);
  await authenticatedPage.goto(`/devices/${deviceId}/settings`);

  // Wait to see what happens
  await authenticatedPage.waitForTimeout(35000); // Wait longer than 30s timeout

  console.log(`\n=== Total API calls made: ${apiCalls.length} ===\n`);

  // Check page content
  const pageText = await authenticatedPage.locator('body').textContent();
  console.log(`\n=== Page shows: ===`);
  if (pageText?.includes('No settings available')) {
    console.log('❌ "No settings available" error shown');
  } else if (pageText?.includes('battery_capacity')) {
    console.log('✅ Settings data is displayed');
  } else {
    console.log('⚠️ Unknown state');
    console.log(pageText?.substring(0, 300));
  }
});
