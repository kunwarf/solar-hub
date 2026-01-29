/**
 * Test Data Helper Utilities
 * Generate test data for E2E tests
 */

/**
 * Generate random email address
 */
export function generateRandomEmail(prefix: string = 'test'): string {
  const timestamp = Date.now();
  const random = Math.floor(Math.random() * 10000);
  return `${prefix}_${timestamp}_${random}@test.com`;
}

/**
 * Generate random username
 */
export function generateRandomUsername(prefix: string = 'user'): string {
  const timestamp = Date.now();
  const random = Math.floor(Math.random() * 10000);
  return `${prefix}_${timestamp}_${random}`;
}

/**
 * Generate random password (meets complexity requirements)
 */
export function generateRandomPassword(): string {
  const length = 12;
  const uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const lowercase = 'abcdefghijklmnopqrstuvwxyz';
  const numbers = '0123456789';
  const special = '!@#$%^&*';

  let password = '';
  password += uppercase[Math.floor(Math.random() * uppercase.length)];
  password += lowercase[Math.floor(Math.random() * lowercase.length)];
  password += numbers[Math.floor(Math.random() * numbers.length)];
  password += special[Math.floor(Math.random() * special.length)];

  const all = uppercase + lowercase + numbers + special;
  for (let i = password.length; i < length; i++) {
    password += all[Math.floor(Math.random() * all.length)];
  }

  // Shuffle password
  return password.split('').sort(() => Math.random() - 0.5).join('');
}

/**
 * Generate random number in range
 */
export function randomNumber(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

/**
 * Generate random string
 */
export function randomString(length: number = 8): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let result = '';
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

/**
 * Generate random device name
 */
export function generateDeviceName(): string {
  const types = ['Solar', 'Inverter', 'Battery', 'Meter', 'Sensor'];
  const locations = ['Rooftop', 'Ground', 'Wall', 'Pole', 'Cabinet'];
  const type = types[Math.floor(Math.random() * types.length)];
  const location = locations[Math.floor(Math.random() * locations.length)];
  const number = randomNumber(1, 99);
  return `${type}-${location}-${number}`;
}

/**
 * Pick random item from array
 */
export function pickRandom<T>(array: T[]): T {
  return array[Math.floor(Math.random() * array.length)];
}

/**
 * Generate unique ID
 */
export function generateUniqueId(): string {
  return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Sanitize string for use in selectors
 */
export function sanitizeForSelector(str: string): string {
  return str.replace(/[^a-zA-Z0-9-_]/g, '-');
}

/**
 * Format number with commas
 */
export function formatNumber(num: number): string {
  return num.toLocaleString('en-US');
}

/**
 * Parse number from formatted string
 */
export function parseNumber(str: string): number {
  return parseFloat(str.replace(/,/g, ''));
}

/**
 * Generate mock energy data
 */
export function generateMockEnergyData(points: number = 24): number[] {
  const data: number[] = [];
  for (let i = 0; i < points; i++) {
    // Simulate solar curve (higher during day)
    const hour = i;
    let value = 0;

    if (hour >= 6 && hour <= 18) {
      // Daytime: use sine curve
      const progress = (hour - 6) / 12;
      value = Math.sin(progress * Math.PI) * randomNumber(3000, 5000);
    } else {
      // Nighttime: minimal or zero
      value = randomNumber(0, 100);
    }

    data.push(Math.round(value));
  }
  return data;
}

/**
 * Deep clone object
 */
export function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

/**
 * Wait for condition to be true
 */
export async function waitForCondition(
  condition: () => boolean | Promise<boolean>,
  timeout: number = 5000,
  interval: number = 100
): Promise<boolean> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    if (await condition()) {
      return true;
    }
    await new Promise(resolve => setTimeout(resolve, interval));
  }

  return false;
}
