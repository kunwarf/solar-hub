/**
 * Date Helper Utilities
 * Common date operations for E2E tests
 */

/**
 * Get today's date in YYYY-MM-DD format
 */
export function getTodayDate(): string {
  const today = new Date();
  return formatDate(today);
}

/**
 * Get yesterday's date in YYYY-MM-DD format
 */
export function getYesterdayDate(): string {
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  return formatDate(yesterday);
}

/**
 * Get date N days ago in YYYY-MM-DD format
 */
export function getDaysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return formatDate(date);
}

/**
 * Get date N days from now in YYYY-MM-DD format
 */
export function getDaysFromNow(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return formatDate(date);
}

/**
 * Format date to YYYY-MM-DD
 */
export function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Format date to readable string (e.g., "January 29, 2026")
 */
export function formatDateReadable(date: Date): string {
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

/**
 * Get start of current month
 */
export function getStartOfMonth(): string {
  const date = new Date();
  date.setDate(1);
  return formatDate(date);
}

/**
 * Get end of current month
 */
export function getEndOfMonth(): string {
  const date = new Date();
  date.setMonth(date.getMonth() + 1, 0);
  return formatDate(date);
}

/**
 * Get date range for last N days
 */
export function getLastNDaysRange(days: number): { start: string; end: string } {
  return {
    start: getDaysAgo(days),
    end: getTodayDate(),
  };
}

/**
 * Parse date string to Date object
 */
export function parseDate(dateString: string): Date {
  return new Date(dateString);
}

/**
 * Check if date is today
 */
export function isToday(date: Date): boolean {
  const today = new Date();
  return (
    date.getDate() === today.getDate() &&
    date.getMonth() === today.getMonth() &&
    date.getFullYear() === today.getFullYear()
  );
}

/**
 * Get timestamp in milliseconds
 */
export function getTimestamp(): number {
  return Date.now();
}

/**
 * Wait for specified milliseconds
 */
export async function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
