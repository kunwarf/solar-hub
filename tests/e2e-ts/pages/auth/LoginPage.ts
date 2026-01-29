import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from '@/pages/base/BasePage';

/**
 * Page object for the Login page
 */
export class LoginPage extends BasePage {
  // Locators
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;
  readonly errorMessage: Locator;
  readonly forgotPasswordLink: Locator;
  readonly signUpLink: Locator;

  constructor(page: Page) {
    super(page);

    // Initialize locators
    this.emailInput = page.locator('input[type="email"]').first();
    this.passwordInput = page.locator('input[type="password"]').first();
    this.submitButton = page.locator('button[type="submit"]').first();
    this.errorMessage = page.getByTestId('error-message');
    this.forgotPasswordLink = page.getByRole('link', { name: /forgot password/i });
    this.signUpLink = page.getByRole('link', { name: /sign up|register/i });
  }

  /**
   * Navigate to login page
   */
  async goto() {
    await this.page.goto('/auth');
    await this.waitForLoaded();
  }

  /**
   * Wait for login page to be fully loaded
   */
  async waitForLoaded() {
    await expect(this.emailInput).toBeVisible();
    await expect(this.passwordInput).toBeVisible();
    await expect(this.submitButton).toBeVisible();
  }

  /**
   * Login with email and password
   */
  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  /**
   * Login and wait for navigation to dashboard
   */
  async loginAndWaitForDashboard(email: string, password: string) {
    await Promise.all([
      this.page.waitForURL(/.*dashboard/, { timeout: 15000 }),
      this.login(email, password),
    ]);
  }

  /**
   * Expect login to be successful (redirected to dashboard)
   */
  async expectLoginSuccess() {
    await expect(this.page).toHaveURL(/.*dashboard/, { timeout: 15000 });

    // Verify token exists
    const token = await this.getLocalStorageItem('token');
    expect(token).toBeTruthy();
  }

  /**
   * Expect error message to be displayed
   */
  async expectErrorMessage(message: string | RegExp) {
    await expect(this.errorMessage).toBeVisible();

    if (typeof message === 'string') {
      await expect(this.errorMessage).toContainText(message);
    } else {
      await expect(this.errorMessage).toContainText(message);
    }
  }

  /**
   * Expect validation errors on empty fields
   */
  async expectValidationErrors() {
    await expect(this.emailInput).toHaveAttribute('aria-invalid', 'true');
    await expect(this.passwordInput).toHaveAttribute('aria-invalid', 'true');
  }

  /**
   * Click forgot password link
   */
  async clickForgotPassword() {
    await this.forgotPasswordLink.click();
  }

  /**
   * Click sign up link
   */
  async clickSignUp() {
    await this.signUpLink.click();
  }

  /**
   * Get email input value
   */
  async getEmailValue(): Promise<string> {
    return await this.emailInput.inputValue();
  }

  /**
   * Get password input value
   */
  async getPasswordValue(): Promise<string> {
    return await this.passwordInput.inputValue();
  }

  /**
   * Check if submit button is disabled
   */
  async isSubmitButtonDisabled(): Promise<boolean> {
    return await this.submitButton.isDisabled();
  }

  /**
   * Clear email field
   */
  async clearEmail() {
    await this.emailInput.clear();
  }

  /**
   * Clear password field
   */
  async clearPassword() {
    await this.passwordInput.clear();
  }
}
