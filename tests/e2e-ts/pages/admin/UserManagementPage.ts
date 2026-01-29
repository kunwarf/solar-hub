import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from '@/pages/base/BasePage';

/**
 * Page object for User Management (Admin)
 * Handles user CRUD operations, role assignments, and permissions
 */
export class UserManagementPage extends BasePage {
  // Main elements
  readonly pageTitle: Locator;
  readonly addUserButton: Locator;
  readonly userTable: Locator;
  readonly searchInput: Locator;
  readonly filterByRole: Locator;

  // User table columns
  readonly nameColumn: Locator;
  readonly emailColumn: Locator;
  readonly roleColumn: Locator;
  readonly statusColumn: Locator;
  readonly actionsColumn: Locator;

  // User form (add/edit)
  readonly userFormDialog: Locator;
  readonly firstNameInput: Locator;
  readonly lastNameInput: Locator;
  readonly emailInput: Locator;
  readonly roleSelect: Locator;
  readonly statusSelect: Locator;
  readonly saveButton: Locator;
  readonly cancelButton: Locator;

  // Actions
  readonly editButtons: Locator;
  readonly deleteButtons: Locator;
  readonly activateButtons: Locator;
  readonly deactivateButtons: Locator;

  // Confirmation dialogs
  readonly confirmDialog: Locator;
  readonly confirmButton: Locator;
  readonly cancelDialogButton: Locator;

  // Messages
  readonly successMessage: Locator;
  readonly errorMessage: Locator;

  // Empty state
  readonly noUsersMessage: Locator;

  constructor(page: Page) {
    super(page);

    // Main elements
    this.pageTitle = page.getByRole('heading', { name: /user.*management|users/i });
    this.addUserButton = page.getByRole('button', { name: /add user|new user|invite user/i });
    this.userTable = page.getByTestId('user-table').or(page.locator('table'));
    this.searchInput = page.getByPlaceholder(/search.*user/i);
    this.filterByRole = page.getByTestId('role-filter');

    // Table columns
    this.nameColumn = page.getByRole('columnheader', { name: /name/i });
    this.emailColumn = page.getByRole('columnheader', { name: /email/i });
    this.roleColumn = page.getByRole('columnheader', { name: /role/i });
    this.statusColumn = page.getByRole('columnheader', { name: /status/i });
    this.actionsColumn = page.getByRole('columnheader', { name: /actions/i });

    // User form
    this.userFormDialog = page.getByRole('dialog').or(page.getByTestId('user-form-dialog'));
    this.firstNameInput = page.getByLabel(/first name/i);
    this.lastNameInput = page.getByLabel(/last name/i);
    this.emailInput = page.getByLabel(/email/i);
    this.roleSelect = page.getByLabel(/role/i);
    this.statusSelect = page.getByLabel(/status/i);
    this.saveButton = page.getByRole('button', { name: /save|create|update/i });
    this.cancelButton = page.getByRole('button', { name: /cancel/i });

    // Actions
    this.editButtons = page.getByRole('button', { name: /edit/i });
    this.deleteButtons = page.getByRole('button', { name: /delete|remove/i });
    this.activateButtons = page.getByRole('button', { name: /activate|enable/i });
    this.deactivateButtons = page.getByRole('button', { name: /deactivate|disable/i });

    // Confirmation
    this.confirmDialog = page.getByRole('dialog').filter({ hasText: /confirm|sure/i });
    this.confirmButton = page.getByRole('button', { name: /confirm|yes|delete/i });
    this.cancelDialogButton = page.getByRole('button', { name: /cancel|no/i });

    // Messages
    this.successMessage = page.getByTestId('success-message').or(page.getByRole('alert').filter({ hasText: /success/i }));
    this.errorMessage = page.getByTestId('error-message').or(page.getByRole('alert').filter({ hasText: /error/i }));

    // Empty state
    this.noUsersMessage = page.getByText(/no users|no results/i);
  }

  /**
   * Navigate to user management page
   */
  async goto() {
    await this.page.goto('/admin/users');
    await this.waitForLoaded();
  }

  /**
   * Wait for page to load
   */
  async waitForLoaded() {
    await this.page.waitForLoadState('domcontentloaded');
    await this.waitForAPIResponse('/api/v1/users').catch(() => null);
  }

  /**
   * Get list of users
   */
  async getUsers(): Promise<string[]> {
    const rows = this.page.locator('tbody tr');
    const count = await rows.count();

    const users: string[] = [];
    for (let i = 0; i < count; i++) {
      const emailCell = rows.nth(i).locator('td').nth(1); // Assuming email is 2nd column
      const text = await emailCell.textContent();
      if (text) users.push(text.trim());
    }

    return users;
  }

  /**
   * Get user count
   */
  async getUserCount(): Promise<number> {
    const rows = this.page.locator('tbody tr');
    return await rows.count();
  }

  /**
   * Search for a user
   */
  async searchUser(email: string) {
    await this.searchInput.fill(email);
    await this.page.waitForTimeout(1000);
  }

  /**
   * Clear search
   */
  async clearSearch() {
    await this.searchInput.clear();
    await this.page.waitForTimeout(500);
  }

  /**
   * Filter users by role
   */
  async filterByRoleType(role: 'owner' | 'admin' | 'viewer' | 'installer') {
    await this.filterByRole.click();
    const option = this.page.getByRole('option', { name: new RegExp(role, 'i') });
    await option.click();
    await this.page.waitForTimeout(1000);
  }

  /**
   * Click add user button
   */
  async clickAddUser() {
    await this.addUserButton.click();
    await expect(this.userFormDialog).toBeVisible();
  }

  /**
   * Create a new user
   */
  async createUser(firstName: string, lastName: string, email: string, role: string) {
    await this.clickAddUser();

    await this.firstNameInput.fill(firstName);
    await this.lastNameInput.fill(lastName);
    await this.emailInput.fill(email);

    if (await this.roleSelect.isVisible()) {
      await this.roleSelect.selectOption({ label: role });
    }

    await this.saveButton.click();

    // Wait for success or form to close
    await Promise.race([
      expect(this.successMessage).toBeVisible({ timeout: 5000 }).catch(() => null),
      expect(this.userFormDialog).not.toBeVisible({ timeout: 5000 }).catch(() => null),
    ]);
  }

  /**
   * Edit a user
   */
  async editUser(email: string) {
    const row = this.page.getByRole('row').filter({ hasText: email });
    const editButton = row.getByRole('button', { name: /edit/i });

    await editButton.click();
    await expect(this.userFormDialog).toBeVisible();
  }

  /**
   * Delete a user
   */
  async deleteUser(email: string) {
    const row = this.page.getByRole('row').filter({ hasText: email });
    const deleteButton = row.getByRole('button', { name: /delete/i });

    await deleteButton.click();

    // Confirm deletion
    if (await this.confirmDialog.isVisible()) {
      await this.confirmButton.click();
    }

    await this.waitForLoaded();
  }

  /**
   * Change user role
   */
  async changeUserRole(email: string, newRole: string) {
    await this.editUser(email);

    if (await this.roleSelect.isVisible()) {
      await this.roleSelect.selectOption({ label: newRole });
      await this.saveButton.click();
    }

    await this.waitForLoaded();
  }

  /**
   * Check if user exists
   */
  async hasUser(email: string): Promise<boolean> {
    const users = await this.getUsers();
    return users.some(user => user.toLowerCase().includes(email.toLowerCase()));
  }

  /**
   * Verify user management page loaded
   */
  async expectUserManagementLoaded() {
    await expect(this.page).toHaveURL(/.*admin.*users/);
    await expect(this.pageTitle).toBeVisible();
  }

  /**
   * Verify add user button is visible (owner/admin only)
   */
  async expectAddUserButtonVisible() {
    await expect(this.addUserButton).toBeVisible();
  }

  /**
   * Verify user in list
   */
  async expectUserInList(email: string) {
    const hasUser = await this.hasUser(email);
    expect(hasUser).toBe(true);
  }

  /**
   * Verify user not in list
   */
  async expectUserNotInList(email: string) {
    const hasUser = await this.hasUser(email);
    expect(hasUser).toBe(false);
  }
}
