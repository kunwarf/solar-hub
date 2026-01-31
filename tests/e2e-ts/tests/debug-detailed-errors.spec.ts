import { test, expect } from '@/fixtures/auth.fixture';

test('debug detailed error flow', async ({ authenticatedPage }) => {
  const deviceId = '669a0686-f574-445d-93cf-7ff1bc078b29';

  // Capture ALL console logs including errors
  authenticatedPage.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    console.log(`[BROWSER-${type.toUpperCase()}] ${text}`);
  });

  // Capture page errors
  authenticatedPage.on('pageerror', error => {
    console.log(`[PAGE-ERROR] ${error.message}`);
    console.log(error.stack);
  });

  // Navigate to settings page
  console.log('\n=== Loading settings page ===\n');
  await authenticatedPage.goto(`/devices/${deviceId}/settings`);

  // Wait for query to complete
  await authenticatedPage.waitForTimeout(10000);

  // Check if settings are displayed
  const bodyText = await authenticatedPage.locator('body').textContent();

  console.log('\n=== Result ===');
  if (bodyText?.includes('No settings available') || bodyText?.includes('Unable to load')) {
    console.log('❌ ERROR STATE - Settings not loaded');

    // Check what's actually shown
    const mainContent = await authenticatedPage.locator('main, .container, [role="main"]').first().textContent();
    console.log('\nPage content:', mainContent?.substring(0, 500));
  } else if (bodyText?.includes('Battery Capacity') || bodyText?.includes('battery_capacity_ah') || bodyText?.includes('1010')) {
    console.log('✅ SUCCESS - Settings are displayed!');
  } else {
    console.log('⚠️ UNKNOWN STATE');
    console.log('Body text sample:', bodyText?.substring(0, 300));
  }
});
