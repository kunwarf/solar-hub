import { test, expect } from '@/fixtures/auth.fixture';

test('debug command status API', async ({ authenticatedPage }) => {
  const deviceId = '669a0686-f574-445d-93cf-7ff1bc078b29';
  const commandId = '00cb0310-3cdb-46d1-817c-70226b7cbb37';

  // Navigate to get cookies/auth
  await authenticatedPage.goto('/devices');
  await authenticatedPage.waitForTimeout(2000);

  // Get the command status using the API context
  const response = await authenticatedPage.request.get(
    `http://182.180.150.107:8000/api/v1/devices/${deviceId}/commands/${commandId}/status`
  );

  console.log('\n=== System A Command Status ===');
  console.log('Status Code:', response.status());
  const data = await response.json();
  console.log('Response:', JSON.stringify(data, null, 2));

  // Also check System B directly
  const systemBResponse = await authenticatedPage.request.get(
    `http://182.180.150.107:8001/api/v1/commands/${commandId}`
  );
  console.log('\n=== System B Command Status ===');
  console.log('Status Code:', systemBResponse.status());
  const systemBData = await systemBResponse.json();
  console.log('Response:', JSON.stringify(systemBData, null, 2));
});
