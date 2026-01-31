import { test } from '@/fixtures/auth.fixture';

test('check System A command status response', async ({ authenticatedPage }) => {
  const deviceId = '669a0686-f574-445d-93cf-7ff1bc078b29';
  const commandId = 'ddeaefd7-4e73-43a0-bfca-1c156e8181b6';

  // Navigate to get auth context
  await authenticatedPage.goto('/devices');
  await authenticatedPage.waitForTimeout(1000);

  // Call System A endpoint
  const systemAResponse = await authenticatedPage.request.get(
    `http://182.180.150.107:8000/api/v1/devices/${deviceId}/commands/${commandId}/status`
  );

  console.log('\n=== System A Response ===');
  console.log('Status Code:', systemAResponse.status());
  const systemAData = await systemAResponse.json();
  console.log('Data:', JSON.stringify(systemAData, null, 2));

  // Call System B endpoint directly
  const systemBResponse = await authenticatedPage.request.get(
    `http://182.180.150.107:8001/api/v1/commands/${commandId}`
  );

  console.log('\n=== System B Response ===');
  console.log('Status Code:', systemBResponse.status());
  const systemBData = await systemBResponse.json();
  console.log('Status:', systemBData.status);
  console.log('Has Result:', !!systemBData.result);
  console.log('Has Settings:', !!systemBData.result?.settings);

  console.log('\n=== Comparison ===');
  console.log('System A status:', systemAData.status);
  console.log('System B status:', systemBData.status);
  console.log('Match:', systemAData.status === systemBData.status ? '✅' : '❌');
});
