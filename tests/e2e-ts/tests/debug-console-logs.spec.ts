import { test, expect } from '@/fixtures/auth.fixture';

test('capture console logs and API response', async ({ authenticatedPage }) => {
  const deviceId = '669a0686-f574-445d-93cf-7ff1bc078b29';
  const consoleLogs: string[] = [];
  let completedResponse: any = null;

  // Capture console logs
  authenticatedPage.on('console', msg => {
    const text = msg.text();
    if (text.includes('DeviceSettings') || text.includes('settings') || text.includes('error') || text.includes('Error')) {
      consoleLogs.push(text);
      console.log(`[CONSOLE] ${text}`);
    }
  });

  // Capture the completed status response
  authenticatedPage.on('response', async (response) => {
    const url = response.url();
    if (url.includes('/commands/') && url.includes('/status')) {
      try {
        const data = await response.json();
        if (data.status === 'completed') {
          completedResponse = data;
          console.log('\n=== COMPLETED RESPONSE ===');
          console.log(JSON.stringify(data, null, 2));
        }
      } catch (e) {
        // Not JSON
      }
    }
  });

  // Navigate to settings page
  await authenticatedPage.goto(`/devices/${deviceId}/settings`);

  // Wait for completion or timeout
  await authenticatedPage.waitForTimeout(10000);

  console.log('\n=== Console logs captured: ===');
  consoleLogs.forEach(log => console.log(log));

  console.log('\n=== Page state: ===');
  const pageText = await authenticatedPage.locator('body').textContent();
  if (pageText?.includes('No settings available')) {
    console.log('❌ Error message shown');
  } else if (pageText?.includes('Battery Capacity')) {
    console.log('✅ Settings displayed');
  } else {
    console.log('⚠️ Unknown state');
  }
});
