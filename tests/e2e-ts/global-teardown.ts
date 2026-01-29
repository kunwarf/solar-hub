import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';

async function globalTeardown(config: FullConfig) {
  console.log('\n🧹 Starting global teardown...\n');

  // Optional: Clean up authentication state files
  // Uncomment if you want to remove auth files after test run
  /*
  const authDir = path.join(__dirname, 'test-results', '.auth');

  if (fs.existsSync(authDir)) {
    const files = fs.readdirSync(authDir);
    files.forEach(file => {
      const filePath = path.join(authDir, file);
      fs.unlinkSync(filePath);
      console.log(`   ✓ Removed ${file}`);
    });
  }
  */

  // Optional: Clean up test data from database
  // Add database cleanup logic here if needed

  console.log('\n✅ Global teardown completed\n');
}

export default globalTeardown;
