import { Page, Locator, expect } from '@playwright/test';

/**
 * Base page class that all page objects should extend
 * Provides common functionality for all pages
 */
export class BasePage {
  readonly page: Page;
  readonly baseURL: string;

  constructor(page: Page) {
    this.page = page;
    this.baseURL = process.env.BASE_URL || 'http://localhost:8081';
  }

  /**
   * Navigate to a specific path
   */
  async goto(path: string, options?: { waitUntil?: 'load' | 'domcontentloaded' | 'networkidle' }) {
    await this.page.goto(path, options);
  }

  /**
   * Wait for page to be fully loaded
   */
  async waitForLoaded() {
    await this.page.waitForLoadState('domcontentloaded');
  }

  /**
   * Wait for network to be idle
   */
  async waitForNetworkIdle() {
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Get element by test ID
   */
  getByTestId(testId: string): Locator {
    return this.page.getByTestId(testId);
  }

  /**
   * Get element by text
   */
  getByText(text: string | RegExp): Locator {
    return this.page.getByText(text);
  }

  /**
   * Get element by role
   */
  getByRole(role: 'button' | 'link' | 'textbox' | 'heading' | 'img', options?: { name?: string | RegExp }): Locator {
    return this.page.getByRole(role, options);
  }

  /**
   * Wait for an API response matching a URL pattern
   */
  async waitForAPIResponse(urlPattern: string | RegExp, options?: { timeout?: number }) {
    return await this.page.waitForResponse(
      (response) => {
        const url = response.url();
        return typeof urlPattern === 'string'
          ? url.includes(urlPattern)
          : urlPattern.test(url);
      },
      options
    );
  }

  /**
   * Wait for multiple API responses
   */
  async waitForMultipleAPIResponses(urlPatterns: (string | RegExp)[]) {
    const promises = urlPatterns.map(pattern => this.waitForAPIResponse(pattern));
    return await Promise.all(promises);
  }

  /**
   * Click element and wait for navigation
   */
  async clickAndNavigate(locator: Locator, expectedURL?: string | RegExp) {
    await Promise.all([
      expectedURL ? this.page.waitForURL(expectedURL) : this.page.waitForLoadState('domcontentloaded'),
      locator.click(),
    ]);
  }

  /**
   * Fill form field and wait for value
   */
  async fillField(locator: Locator, value: string) {
    await locator.fill(value);
    await expect(locator).toHaveValue(value);
  }

  /**
   * Check if element is visible
   */
  async isVisible(locator: Locator): Promise<boolean> {
    try {
      await expect(locator).toBeVisible({ timeout: 5000 });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Get current URL
   */
  async getCurrentURL(): Promise<string> {
    return this.page.url();
  }

  /**
   * Take screenshot
   */
  async takeScreenshot(name: string) {
    await this.page.screenshot({ path: `screenshots/${name}.png`, fullPage: true });
  }

  /**
   * Reload page
   */
  async reload() {
    await this.page.reload();
  }

  /**
   * Go back
   */
  async goBack() {
    await this.page.goBack();
  }

  /**
   * Wait for element to be visible
   */
  async waitForElement(locator: Locator, options?: { timeout?: number }) {
    await expect(locator).toBeVisible(options);
  }

  /**
   * Wait for element to be hidden
   */
  async waitForElementHidden(locator: Locator, options?: { timeout?: number }) {
    await expect(locator).toBeHidden(options);
  }

  /**
   * Get local storage item
   */
  async getLocalStorageItem(key: string): Promise<string | null> {
    return await this.page.evaluate((key) => localStorage.getItem(key), key);
  }

  /**
   * Set local storage item
   */
  async setLocalStorageItem(key: string, value: string) {
    await this.page.evaluate(
      ({ key, value }) => localStorage.setItem(key, value),
      { key, value }
    );
  }

  /**
   * Clear local storage
   */
  async clearLocalStorage() {
    await this.page.evaluate(() => localStorage.clear());
  }

  /**
   * Get session storage item
   */
  async getSessionStorageItem(key: string): Promise<string | null> {
    return await this.page.evaluate((key) => sessionStorage.getItem(key), key);
  }

  /**
   * Check if user is authenticated
   */
  async isAuthenticated(): Promise<boolean> {
    const token = await this.getLocalStorageItem('token');
    return token !== null && token.length > 0;
  }

  /**
   * Logout user
   */
  async logout() {
    await this.clearLocalStorage();
    await this.page.evaluate(() => sessionStorage.clear());
  }
}
