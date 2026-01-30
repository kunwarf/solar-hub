/**
 * Seed Test Users Script
 *
 * Creates test users for E2E testing in the local database.
 * Run this before running E2E tests locally.
 *
 * Usage:  ts-node scripts/seed-test-users.ts
 */

import axios from 'axios';
import dotenv from 'dotenv';
import path from 'path';

// Load environment
dotenv.config({ path: path.resolve(__dirname, '..', '.env.local') });

const API_URL = process.env.API_SYSTEM_A_URL || 'http://localhost:8000';

interface TestUser {
  email: string;
  password: string;
  full_name: string;
  role: string;
}

const TEST_USERS: TestUser[] = [
  {
    email: 'owner@solarhub.local',
    password: 'Test@123',
    full_name: 'Test Owner',
    role: 'owner',
  },
  {
    email: 'admin@solarhub.local',
    password: 'Test@123',
    full_name: 'Test Admin',
    role: 'admin',
  },
  {
    email: 'viewer@solarhub.local',
    password: 'Test@123',
    full_name: 'Test Viewer',
    role: 'viewer',
  },
  {
    email: 'installer@solarhub.local',
    password: 'Test@123',
    full_name: 'Test Installer',
    role: 'installer',
  },
];

async function seedTestUsers() {
  console.log('🌱 Seeding test users for E2E testing...\n');
  console.log(`API URL: ${API_URL}\n`);

  for (const user of TEST_USERS) {
    try {
      console.log(`Creating user: ${user.email}...`);

      // Try to create user via API (if signup endpoint exists)
      try {
        const response = await axios.post(`${API_URL}/api/v1/auth/signup`, {
          email: user.email,
          password: user.password,
          full_name: user.full_name,
        });

        if (response.status === 200 || response.status === 201) {
          console.log(`  ✓ User created: ${user.email}`);
          continue;
        }
      } catch (apiError: any) {
        if (apiError.response?.status === 409 || apiError.response?.data?.detail?.includes('already exists')) {
          console.log(`  ℹ User already exists: ${user.email}`);
          continue;
        }

        // If signup endpoint doesn't exist, we'll need to use direct DB access
        if (apiError.response?.status === 404) {
          console.log(`  ⚠ Signup API not available, will use direct DB access`);
          throw new Error('Need DB access');
        }

        throw apiError;
      }
    } catch (error: any) {
      console.error(`  ✗ Failed to create user ${user.email}:`, error.message);
    }
  }

  console.log('\n✅ Test user seeding completed\n');
  console.log('You can now use these credentials for testing:');
  TEST_USERS.forEach(user => {
    console.log(`  ${user.role}: ${user.email} / ${user.password}`);
  });
}

// Alternative: Direct database seeding using SQL
async function seedViaDatabase() {
  console.log('\n📝 Creating SQL seed script...\n');

  const sqlScript = `
-- Test Users for E2E Testing
-- Password is 'Test@123' (hashed)

-- Note: You need to hash passwords using bcrypt with cost factor 12
-- The hash below is for 'Test@123'

INSERT INTO users (id, email, password_hash, full_name, role, is_active, created_at, updated_at)
VALUES
  (gen_random_uuid(), 'owner@solarhub.local', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5koTb8O4.d3c2', 'Test Owner', 'owner', true, NOW(), NOW()),
  (gen_random_uuid(), 'admin@solarhub.local', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5koTb8O4.d3c2', 'Test Admin', 'admin', true, NOW(), NOW()),
  (gen_random_uuid(), 'viewer@solarhub.local', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5koTb8O4.d3c2', 'Test Viewer', 'viewer', true, NOW(), NOW()),
  (gen_random_uuid(), 'installer@solarhub.local', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5koTb8O4.d3c2', 'Test Installer', 'installer', true, NOW(), NOW())
ON CONFLICT (email) DO NOTHING;
  `.trim();

  const scriptPath = path.join(__dirname, '..', 'test-results', 'seed-users.sql');
  const fs = require('fs');
  fs.writeFileSync(scriptPath, sqlScript);

  console.log(`SQL script saved to: ${scriptPath}\n`);
  console.log('Run this command to seed the database:');
  console.log(`  psql -h localhost -p 5432 -U postgres -d solar_hub_dev -f ${scriptPath}\n`);
}

// Run seeding
if (require.main === module) {
  seedTestUsers()
    .then(() => seedViaDatabase())
    .catch((error) => {
      console.error('\n❌ Seeding failed:', error);
      process.exit(1);
    });
}

export { seedTestUsers, TEST_USERS };
