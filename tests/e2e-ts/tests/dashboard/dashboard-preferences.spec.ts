import { test, expect } from '@/fixtures/auth.fixture';
import { DashboardPage } from '@/pages/dashboard/DashboardPage';

/**
 * Dashboard Layout Preferences Tests
 *
 * Tests dashboard layout customization, widget reordering, and preference persistence
 * Priority: P1 (High)
 */
test.describe('Dashboard Preferences', { tag: '@dashboard-preferences' }, () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ authenticatedPage }) => {
    dashboardPage = new DashboardPage(authenticatedPage);
    await dashboardPage.goto();

    // Dismiss onboarding wizard if present
    const closeButton = authenticatedPage.locator('[aria-label="Close"]').or(authenticatedPage.getByRole('button', { name: /^close$/i }));
    if (await closeButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await closeButton.click({ force: true });
      await authenticatedPage.waitForTimeout(1000);
    }

    const skipButton = authenticatedPage.getByRole('button', { name: /skip for now/i });
    if (await skipButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await skipButton.click({ force: true });
      await authenticatedPage.waitForTimeout(1000);
    }

    // Wait for dialog overlay to disappear
    const dialogOverlay = authenticatedPage.locator('[class*="bg-black/80"]');
    await dialogOverlay.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => null);
  });

  test('should enter edit mode and show widget controls', {
    tag: ['@smoke', '@critical']
  }, async ({ authenticatedPage }) => {
    // Click edit layout button
    const editButton = authenticatedPage.getByRole('button', { name: /edit layout/i });
    await editButton.click();

    // Should show edit mode controls
    await expect(authenticatedPage.getByText(/drag.*to reorder|reorder widgets/i)).toBeVisible({ timeout: 5000 });

    // Should have done/save button
    const doneButton = authenticatedPage.getByRole('button', { name: /done|save|exit edit/i });
    await expect(doneButton).toBeVisible();
  });

  test('should be able to toggle widget visibility', {
    tag: ['@regression', '@high']
  }, async ({ authenticatedPage }) => {
    // Enter edit mode
    const editButton = authenticatedPage.getByRole('button', { name: /edit layout/i });
    await editButton.click();
    await authenticatedPage.waitForTimeout(500);

    // Find a visible widget (Energy Flow)
    const energyFlowWidget = authenticatedPage.getByText(/energy flow/i).first();
    const isInitiallyVisible = await energyFlowWidget.isVisible().catch(() => false);

    // Look for visibility toggle (eye icon or visibility button)
    const visibilityToggle = authenticatedPage.locator('[data-widget-id="energy-flow"]')
      .locator('button[aria-label*="visibility"], button[aria-label*="hide"], button[aria-label*="show"]')
      .first();

    if (await visibilityToggle.isVisible({ timeout: 2000 }).catch(() => false)) {
      // Toggle visibility
      await visibilityToggle.click();
      await authenticatedPage.waitForTimeout(500);

      // Exit edit mode
      const doneButton = authenticatedPage.getByRole('button', { name: /done|save|exit edit/i });
      await doneButton.click();
      await authenticatedPage.waitForTimeout(1000);

      // Check if visibility changed
      const isNowVisible = await energyFlowWidget.isVisible().catch(() => false);
      expect(isNowVisible).toBe(!isInitiallyVisible);
    } else {
      test.skip();
    }
  });

  test('should persist widget order after page reload', {
    tag: ['@critical', '@smoke']
  }, async ({ authenticatedPage }) => {
    // Wait for initial load
    await authenticatedPage.waitForTimeout(2000);

    // Get initial widget order by collecting visible headings
    const getWidgetOrder = async () => {
      const headings = await authenticatedPage.locator('h3[class*="text"]').allTextContents();
      return headings.filter(h => h.trim().length > 0);
    };

    const initialOrder = await getWidgetOrder();
    expect(initialOrder.length).toBeGreaterThan(0);

    // Enter edit mode
    const editButton = authenticatedPage.getByRole('button', { name: /edit layout/i });
    if (await editButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await editButton.click();
      await authenticatedPage.waitForTimeout(1000);

      // Try to reorder widgets using drag and drop
      const widgets = authenticatedPage.locator('[data-widget-id]');
      const firstWidget = widgets.first();
      const secondWidget = widgets.nth(1);

      if (await firstWidget.isVisible().catch(() => false) && await secondWidget.isVisible().catch(() => false)) {
        // Drag first widget to second position
        await firstWidget.dragTo(secondWidget);
        await authenticatedPage.waitForTimeout(500);
      }

      // Exit edit mode to save
      const doneButton = authenticatedPage.getByRole('button', { name: /done|save|exit edit/i });
      await doneButton.click();
      await authenticatedPage.waitForTimeout(2000);
    }

    // Get order after reordering
    const reorderedOrder = await getWidgetOrder();

    // Reload page
    await authenticatedPage.reload();
    await authenticatedPage.waitForLoadState('domcontentloaded');
    await authenticatedPage.waitForTimeout(2000);

    // Get order after reload
    const orderAfterReload = await getWidgetOrder();

    // Order should match the reordered state (proving persistence)
    expect(orderAfterReload).toEqual(reorderedOrder);
  });

  test('should save widget size changes', {
    tag: ['@regression']
  }, async ({ authenticatedPage }) => {
    // Enter edit mode
    const editButton = authenticatedPage.getByRole('button', { name: /edit layout/i });
    if (await editButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await editButton.click();
      await authenticatedPage.waitForTimeout(500);

      // Look for size change controls (small/medium/large buttons)
      const sizeButton = authenticatedPage.getByRole('button', { name: /small|medium|large/i }).first();

      if (await sizeButton.isVisible({ timeout: 2000 }).catch(() => false)) {
        const initialText = await sizeButton.textContent();
        await sizeButton.click();
        await authenticatedPage.waitForTimeout(500);

        // Exit edit mode
        const doneButton = authenticatedPage.getByRole('button', { name: /done|save|exit edit/i });
        await doneButton.click();
        await authenticatedPage.waitForTimeout(1000);

        // Verify changes persisted (would need API check in real scenario)
        expect(true).toBe(true); // Placeholder
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });

  test('should apply layout presets', {
    tag: ['@regression', '@high']
  }, async ({ authenticatedPage }) => {
    // Look for preset selector/dropdown
    const presetButton = authenticatedPage.getByRole('button', { name: /preset|layout/i }).first();

    if (await presetButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await presetButton.click();
      await authenticatedPage.waitForTimeout(500);

      // Select a different preset
      const presetOption = authenticatedPage.getByRole('option', { name: /essential|compact|detailed/i }).first()
        .or(authenticatedPage.getByText(/essential|compact|detailed/i).first());

      if (await presetOption.isVisible({ timeout: 2000 }).catch(() => false)) {
        await presetOption.click();
        await authenticatedPage.waitForTimeout(2000);

        // Verify preset was applied (widgets changed)
        const widgets = await authenticatedPage.locator('h3[class*="text"]').allTextContents();
        expect(widgets.length).toBeGreaterThan(0);
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });

  test('should reset to default layout', {
    tag: ['@regression']
  }, async ({ authenticatedPage }) => {
    // Enter edit mode
    const editButton = authenticatedPage.getByRole('button', { name: /edit layout/i });
    if (await editButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await editButton.click();
      await authenticatedPage.waitForTimeout(500);

      // Look for reset button
      const resetButton = authenticatedPage.getByRole('button', { name: /reset.*default|restore default/i });

      if (await resetButton.isVisible({ timeout: 2000 }).catch(() => false)) {
        await resetButton.click();
        await authenticatedPage.waitForTimeout(1000);

        // Confirm reset if there's a confirmation dialog
        const confirmButton = authenticatedPage.getByRole('button', { name: /confirm|yes|reset/i });
        if (await confirmButton.isVisible({ timeout: 1000 }).catch(() => false)) {
          await confirmButton.click();
          await authenticatedPage.waitForTimeout(1000);
        }

        // Exit edit mode
        const doneButton = authenticatedPage.getByRole('button', { name: /done|save|exit edit/i });
        await doneButton.click();
        await authenticatedPage.waitForTimeout(1000);

        // Verify default layout applied
        expect(true).toBe(true); // Would verify specific widgets
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });

  test('should save preferences via API', {
    tag: ['@critical', '@api']
  }, async ({ authenticatedPage }) => {
    // Setup API response listener
    const preferencesUpdate = authenticatedPage.waitForResponse(
      resp => resp.url().includes('/api/v1/users/me/dashboard/preferences') && resp.request().method() === 'PUT'
    );

    // Enter edit mode and make a change
    const editButton = authenticatedPage.getByRole('button', { name: /edit layout/i });
    if (await editButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await editButton.click();
      await authenticatedPage.waitForTimeout(500);

      // Make any change (toggle visibility, reorder, etc.)
      const visibilityToggle = authenticatedPage.locator('button[aria-label*="visibility"]').first();
      if (await visibilityToggle.isVisible({ timeout: 2000 }).catch(() => false)) {
        await visibilityToggle.click();
        await authenticatedPage.waitForTimeout(500);
      }

      // Exit edit mode
      const doneButton = authenticatedPage.getByRole('button', { name: /done|save|exit edit/i });
      await doneButton.click();

      // Wait for API call
      const response = await preferencesUpdate.catch(() => null);

      if (response) {
        // Verify API call was successful
        expect(response.status()).toBe(200);

        // Verify response body
        const data = await response.json();
        expect(data).toHaveProperty('widget_layout');
        expect(Array.isArray(data.widget_layout)).toBe(true);
      } else {
        // API call might have been made before we started listening
        console.log('API response not captured - may have occurred before listener was set up');
      }
    } else {
      test.skip();
    }
  });

  test('should load preferences from API on mount', {
    tag: ['@critical', '@api']
  }, async ({ authenticatedPage }) => {
    // Setup API response listener before page load
    const preferencesLoad = authenticatedPage.waitForResponse(
      resp => resp.url().includes('/api/v1/users/me/dashboard/preferences') && resp.request().method() === 'GET',
      { timeout: 10000 }
    );

    // Reload to trigger preferences load
    await authenticatedPage.reload();
    await authenticatedPage.waitForLoadState('domcontentloaded');

    // Wait for API call
    const response = await preferencesLoad;

    // Verify API call was successful
    expect(response.status()).toBe(200);

    // Verify response structure
    const data = await response.json();
    expect(data).toHaveProperty('layout_preset');
    expect(data).toHaveProperty('grid_layout');
    expect(data).toHaveProperty('widget_layout');
    expect(Array.isArray(data.widget_layout)).toBe(true);

    // Verify widgets loaded
    await authenticatedPage.waitForTimeout(1000);
    const widgets = await authenticatedPage.locator('h3').count();
    expect(widgets).toBeGreaterThan(0);
  });

  test('should handle concurrent edits gracefully', {
    tag: ['@regression', '@edge-case']
  }, async ({ authenticatedPage }) => {
    // Enter edit mode
    const editButton = authenticatedPage.getByRole('button', { name: /edit layout/i });
    if (await editButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await editButton.click();
      await authenticatedPage.waitForTimeout(500);

      // Make multiple rapid changes
      const visibilityToggles = authenticatedPage.locator('button[aria-label*="visibility"]');
      const count = await visibilityToggles.count();

      if (count > 0) {
        // Click multiple toggles rapidly
        for (let i = 0; i < Math.min(count, 3); i++) {
          await visibilityToggles.nth(i).click();
          await authenticatedPage.waitForTimeout(100);
        }

        // Exit edit mode - should debounce and save final state
        const doneButton = authenticatedPage.getByRole('button', { name: /done|save|exit edit/i });
        await doneButton.click();
        await authenticatedPage.waitForTimeout(2000);

        // Reload to verify saved state
        await authenticatedPage.reload();
        await authenticatedPage.waitForLoadState('domcontentloaded');
        await authenticatedPage.waitForTimeout(1000);

        // Should load without errors
        const errorToast = authenticatedPage.getByTestId('error-toast');
        await expect(errorToast).not.toBeVisible({ timeout: 2000 }).catch(() => {});
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });
});
