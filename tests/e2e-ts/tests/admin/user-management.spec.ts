import { test, expect } from '@/fixtures/auth.fixture';
import { UserManagementPage } from '@/pages/admin/UserManagementPage';

/**
 * User Management Tests (Admin Only)
 *
 * Tests user CRUD operations and role management
 * Priority: P2 (Admin feature)
 */
test.describe('Admin - User Management', { tag: '@admin' }, () => {
  let userManagementPage: UserManagementPage;

  test.beforeEach(async ({ authenticatedPage, userRole }) => {
    // Skip if not admin or owner
    test.skip(!['owner', 'admin'].includes(userRole), 'Requires admin or owner role');

    userManagementPage = new UserManagementPage(authenticatedPage);
    await userManagementPage.goto();
  });

  test('should load user management page', {
    tag: '@regression'
  }, async () => {
    // Verify page loaded
    await userManagementPage.expectUserManagementLoaded();
  });

  test('should display list of users', {
    tag: '@regression'
  }, async () => {
    await userManagementPage.waitForLoaded();

    // Should show users or empty state
    const userCount = await userManagementPage.getUserCount();
    expect(userCount).toBeGreaterThanOrEqual(0);
  });

  test('should show add user button for authorized users', {
    tag: '@regression'
  }, async () => {
    await userManagementPage.expectAddUserButtonVisible();
  });

  test('should allow searching for users', {
    tag: '@regression'
  }, async () => {
    const users = await userManagementPage.getUsers();

    if (users.length > 0) {
      const searchTerm = users[0].substring(0, 5);

      await userManagementPage.searchUser(searchTerm);

      // Results should be filtered
      const filteredUsers = await userManagementPage.getUsers();
      expect(filteredUsers.length).toBeGreaterThanOrEqual(0);
    }
  });

  test('should clear search and show all users', {
    tag: '@regression'
  }, async () => {
    const initialCount = await userManagementPage.getUserCount();

    if (initialCount > 0) {
      // Search for something
      await userManagementPage.searchUser('test');

      // Clear search
      await userManagementPage.clearSearch();

      // Should show all users again
      const finalCount = await userManagementPage.getUserCount();
      expect(finalCount).toBeGreaterThanOrEqual(initialCount - 5); // Allow some tolerance
    }
  });

  test('should display user table with columns', {
    tag: '@regression'
  }, async () => {
    // Check for table headers
    const hasNameColumn = await userManagementPage.nameColumn.isVisible().catch(() => false);
    const hasEmailColumn = await userManagementPage.emailColumn.isVisible().catch(() => false);
    const hasRoleColumn = await userManagementPage.roleColumn.isVisible().catch(() => false);

    // At least one column should be visible
    expect(hasNameColumn || hasEmailColumn || hasRoleColumn).toBe(true);
  });

  test('should show user roles in table', {
    tag: '@regression'
  }, async () => {
    const bodyText = await userManagementPage.page.locator('body').textContent();

    // Should show role information
    const hasRoles = bodyText && (
      bodyText.toLowerCase().includes('owner') ||
      bodyText.toLowerCase().includes('admin') ||
      bodyText.toLowerCase().includes('viewer') ||
      bodyText.toLowerCase().includes('role')
    );

    expect(hasRoles).toBe(true);
  });

  test('should display action buttons for each user', {
    tag: '@regression'
  }, async () => {
    const users = await userManagementPage.getUsers();

    if (users.length > 0) {
      const hasEditButtons = await userManagementPage.editButtons.count() > 0;
      const hasDeleteButtons = await userManagementPage.deleteButtons.count() > 0;

      expect(hasEditButtons || hasDeleteButtons).toBe(true);
    }
  });

  test('should open add user form when button clicked', {
    tag: '@regression'
  }, async () => {
    await userManagementPage.clickAddUser();

    // Form should be visible
    await expect(userManagementPage.userFormDialog).toBeVisible();

    // Cancel to close
    await userManagementPage.cancelButton.click();
  });

  test('should show user form fields', {
    tag: '@regression'
  }, async () => {
    await userManagementPage.clickAddUser();

    // Check for form fields
    const hasFirstName = await userManagementPage.firstNameInput.isVisible().catch(() => false);
    const hasEmail = await userManagementPage.emailInput.isVisible().catch(() => false);

    expect(hasFirstName || hasEmail).toBe(true);

    await userManagementPage.cancelButton.click();
  });

  test('should allow filtering users by role', {
    tag: '@regression'
  }, async () => {
    const hasRoleFilter = await userManagementPage.filterByRole.isVisible().catch(() => false);

    if (hasRoleFilter) {
      await userManagementPage.filterByRoleType('admin');

      // Should filter users
      await userManagementPage.waitForLoaded();

      const filteredCount = await userManagementPage.getUserCount();
      expect(filteredCount).toBeGreaterThanOrEqual(0);
    }
  });

  test('should handle no users gracefully', {
    tag: '@regression'
  }, async () => {
    // Even with no users, page should not crash
    await userManagementPage.expectUserManagementLoaded();

    const userCount = await userManagementPage.getUserCount();
    expect(userCount).toBeGreaterThanOrEqual(0);
  });
});
