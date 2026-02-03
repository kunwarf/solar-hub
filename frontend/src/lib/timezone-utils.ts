/**
 * Timezone utility functions for Solar Hub frontend.
 *
 * Ensures all date/time operations use site timezone, not browser local timezone.
 */

/**
 * Convert UTC date to site local date.
 *
 * @param utcDate - Date in UTC
 * @param siteTimezone - Site timezone (e.g., "Asia/Karachi")
 * @returns Date object adjusted to site timezone
 */
export function convertToSiteTimezone(utcDate: Date, siteTimezone: string): Date {
  // Get site timezone offset using Intl API
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: siteTimezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });

  const parts = formatter.formatToParts(utcDate);
  const dateMap: Record<string, string> = {};
  parts.forEach(part => {
    if (part.type !== 'literal') {
      dateMap[part.type] = part.value;
    }
  });

  return new Date(
    parseInt(dateMap.year),
    parseInt(dateMap.month) - 1,
    parseInt(dateMap.day),
    parseInt(dateMap.hour),
    parseInt(dateMap.minute),
    parseInt(dateMap.second)
  );
}

/**
 * Get current date in site timezone.
 *
 * @param siteTimezone - Site timezone (e.g., "Asia/Karachi")
 * @returns Date object representing "now" in site timezone
 */
export function getSiteNow(siteTimezone: string): Date {
  return convertToSiteTimezone(new Date(), siteTimezone);
}

/**
 * Get the start of month in site timezone.
 *
 * @param date - Reference date
 * @param siteTimezone - Site timezone
 * @returns Date object for first day of month at 00:00 in site timezone
 */
export function getStartOfMonth(date: Date, siteTimezone: string): Date {
  const siteDate = convertToSiteTimezone(date, siteTimezone);
  return new Date(siteDate.getFullYear(), siteDate.getMonth(), 1);
}

/**
 * Get the end of month in site timezone.
 *
 * @param date - Reference date
 * @param siteTimezone - Site timezone
 * @returns Date object for last day of month at 23:59:59 in site timezone
 */
export function getEndOfMonth(date: Date, siteTimezone: string): Date {
  const siteDate = convertToSiteTimezone(date, siteTimezone);
  return new Date(siteDate.getFullYear(), siteDate.getMonth() + 1, 0, 23, 59, 59);
}

/**
 * Calculate billing period based on anchor day in site timezone.
 *
 * @param referenceDate - Reference date (usually "now")
 * @param anchorDay - Billing cycle anchor day (1-28)
 * @param siteTimezone - Site timezone
 * @returns Object with periodStart and periodEnd dates
 */
export function getBillingPeriod(
  referenceDate: Date,
  anchorDay: number,
  siteTimezone: string
): { periodStart: Date; periodEnd: Date } {
  const siteDate = convertToSiteTimezone(referenceDate, siteTimezone);
  const siteDateOfMonth = siteDate.getDate();

  let periodStart: Date;
  let periodEnd: Date;

  if (siteDateOfMonth >= anchorDay) {
    // Current billing cycle
    periodStart = new Date(siteDate.getFullYear(), siteDate.getMonth(), anchorDay);
    periodEnd = new Date(siteDate.getFullYear(), siteDate.getMonth() + 1, anchorDay - 1);
  } else {
    // Previous billing cycle
    periodStart = new Date(siteDate.getFullYear(), siteDate.getMonth() - 1, anchorDay);
    periodEnd = new Date(siteDate.getFullYear(), siteDate.getMonth(), anchorDay - 1);
  }

  return { periodStart, periodEnd };
}

/**
 * Format date in site timezone for display.
 *
 * @param date - Date to format
 * @param siteTimezone - Site timezone
 * @param options - Intl.DateTimeFormatOptions
 * @returns Formatted date string
 */
export function formatInSiteTimezone(
  date: Date,
  siteTimezone: string,
  options?: Intl.DateTimeFormatOptions
): string {
  return date.toLocaleString('en-US', {
    ...options,
    timeZone: siteTimezone,
  });
}

/**
 * Convert date to YYYY-MM-DD string in site timezone.
 *
 * @param date - Date to convert
 * @param siteTimezone - Site timezone
 * @returns Date string in YYYY-MM-DD format
 */
export function toDateString(date: Date, siteTimezone: string): string {
  const siteDate = convertToSiteTimezone(date, siteTimezone);
  const year = siteDate.getFullYear();
  const month = String(siteDate.getMonth() + 1).padStart(2, '0');
  const day = String(siteDate.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Get hour in site timezone from timestamp.
 *
 * @param timestamp - ISO timestamp string or Date
 * @param siteTimezone - Site timezone
 * @returns Hour in site timezone (0-23)
 */
export function getHourInSiteTimezone(timestamp: string | Date, siteTimezone: string): number {
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
  const siteDate = convertToSiteTimezone(date, siteTimezone);
  return siteDate.getHours();
}
