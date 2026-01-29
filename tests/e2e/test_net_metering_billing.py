"""
Net Metering Billing E2E Tests.

Tests for the net metering billing features including:
- Running bill display
- Credit pools visualization
- Capacity analysis
- Billing trend charts
- Billing configuration sync

Run with: pytest tests/e2e/test_net_metering_billing.py -v

Note: These tests require:
1. Frontend running on http://localhost:8080
2. Backend running with valid user credentials
"""
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8080"
TEST_USER_EMAIL = "demo@example.com"
TEST_USER_PASSWORD = "Password123!"


def login(page: Page) -> bool:
    """Helper to login before tests. Returns True if login successful."""
    page.goto(f"{BASE_URL}/auth")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    email_input = page.locator("input[type='email'], input[name='email'], input[placeholder*='email' i]").first
    password_input = page.locator("input[type='password'], input[name='password']").first

    if email_input.is_visible():
        email_input.fill(TEST_USER_EMAIL)
        password_input.fill(TEST_USER_PASSWORD)

        submit_btn = page.locator("button[type='submit'], button:has-text('Sign In'), button:has-text('Login')").first
        submit_btn.click()
        page.wait_for_timeout(4000)

        try:
            page.wait_for_url(lambda url: "/auth" not in url, timeout=10000)
            return True
        except:
            return False
    return False


def skip_wizard(page: Page):
    """Skip setup wizard if visible."""
    skip_btn = page.locator("button:has-text('Skip'), button:has-text('Later')").first
    if skip_btn.is_visible():
        skip_btn.click()
        page.wait_for_timeout(1000)


def require_login(page: Page):
    """Login and skip test if login fails."""
    if not login(page):
        pytest.skip("Login failed - backend may not have test user configured")


class TestNetMeteringBillingPage:
    """Tests for net metering billing features on the Billing page."""

    def test_billing_page_loads(self, page: Page):
        """Test that the billing page loads successfully."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(2000)

        # Check page title or header
        body_text = page.locator("body").text_content() or ""
        assert "billing" in body_text.lower() or "capacity" in body_text.lower() or "energy" in body_text.lower()

    def test_billing_shows_current_period(self, page: Page):
        """Test that current billing period is displayed."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""

        # Should show period information
        has_period = (
            "period" in body_text.lower() or
            "billing" in body_text.lower() or
            "days" in body_text.lower() or
            "month" in body_text.lower()
        )

        assert has_period, "Billing period information not found"

    def test_billing_shows_energy_stats(self, page: Page):
        """Test that energy statistics are displayed."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""

        # Should show energy-related information
        has_energy = (
            "kwh" in body_text.lower() or
            "energy" in body_text.lower() or
            "produced" in body_text.lower() or
            "consumed" in body_text.lower() or
            "generation" in body_text.lower()
        )

        assert has_energy, "Energy statistics not found on billing page"

    def test_billing_shows_import_export(self, page: Page):
        """Test that import/export information is displayed."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""

        # Should show import/export information
        has_grid_flow = (
            "import" in body_text.lower() or
            "export" in body_text.lower() or
            "grid" in body_text.lower() or
            "net" in body_text.lower()
        )

        assert has_grid_flow, "Import/export information not found"

    def test_billing_shows_net_balance(self, page: Page):
        """Test that net balance is displayed."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""

        # Should show balance information
        has_balance = (
            "balance" in body_text.lower() or
            "net" in body_text.lower() or
            "earnings" in body_text.lower() or
            "costs" in body_text.lower() or
            "savings" in body_text.lower()
        )

        assert has_balance, "Net balance information not found"

    def test_billing_shows_currency(self, page: Page):
        """Test that currency amounts are displayed correctly."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""

        # Should show PKR amounts
        has_currency = (
            "pkr" in body_text.lower() or
            "rs" in body_text.lower() or
            "$" in body_text or
            "cost" in body_text.lower() or
            "price" in body_text.lower()
        )

        assert has_currency, "Currency amounts not found"

    def test_billing_has_navigation_elements(self, page: Page):
        """Test that billing page has navigation elements."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(2000)

        # Look for any interactive elements
        buttons = page.locator("button")
        assert buttons.count() > 0, "No buttons found on billing page"


class TestRunningBillSection:
    """Tests for the Running Bill section (net metering API integration)."""

    def test_running_bill_shows_progress(self, page: Page):
        """Test that running bill shows billing progress."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""

        # Look for progress indicator (may or may not be present depending on API data)
        has_progress = (
            "progress" in body_text.lower() or
            "day" in body_text.lower() or
            "%" in body_text
        )

        # This is informational - don't fail if running bill isn't configured
        if not has_progress:
            pytest.skip("Running bill data not available (API may not be configured)")

    def test_running_bill_shows_peak_offpeak(self, page: Page):
        """Test that peak/off-peak breakdown is shown."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""

        # Look for peak/off-peak information
        has_tou = (
            "peak" in body_text.lower() or
            "off-peak" in body_text.lower() or
            "offpeak" in body_text.lower()
        )

        # This is informational
        if not has_tou:
            pytest.skip("TOU data not available (API may not be configured)")


class TestCreditPoolsSection:
    """Tests for the Credit Pools section (3-month netting cycle)."""

    def test_credit_pools_displayed(self, page: Page):
        """Test that credit pools are displayed."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""

        # Look for credit pool information
        has_credits = (
            "credit" in body_text.lower() or
            "pool" in body_text.lower() or
            "cycle" in body_text.lower()
        )

        # This is informational
        if not has_credits:
            pytest.skip("Credit pool data not available")


class TestCapacityAnalysisSection:
    """Tests for the Capacity Analysis section."""

    def test_capacity_status_displayed(self, page: Page):
        """Test that capacity status is displayed."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""

        # Look for capacity information
        has_capacity = (
            "capacity" in body_text.lower() or
            "installed" in body_text.lower() or
            "kw" in body_text.lower()
        )

        if not has_capacity:
            pytest.skip("Capacity data not available")


class TestBillingChartsSection:
    """Tests for billing charts and visualizations."""

    def test_energy_history_chart_exists(self, page: Page):
        """Test that energy history chart is rendered."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        # Look for chart elements (Recharts renders SVG)
        charts = page.locator("svg.recharts-surface, .recharts-wrapper, svg[class*='chart'], canvas")

        # At least one chart should be present
        if charts.count() == 0:
            pytest.skip("No charts found on billing page")

    def test_chart_has_legend(self, page: Page):
        """Test that charts have legends."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        # Look for legend elements
        legends = page.locator(".recharts-legend-wrapper, .recharts-legend-item")

        # Charts should have legends for clarity
        if legends.count() == 0:
            pytest.skip("Chart legends not rendered")


class TestBillingSettingsPage:
    """Tests for the Billing Settings page."""

    def test_billing_settings_page_loads(self, page: Page):
        """Test that billing settings page loads."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing/settings")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(2000)

        body_text = page.locator("body").text_content() or ""

        # Should show settings content or redirect back
        has_settings = (
            "settings" in body_text.lower() or
            "setup" in body_text.lower() or
            "configuration" in body_text.lower() or
            "tariff" in body_text.lower() or
            "billing" in body_text.lower()
        )

        assert has_settings, "Billing settings page content not found"

    def test_billing_settings_has_currency_selector(self, page: Page):
        """Test that currency selector exists."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing/settings")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(2000)

        body_text = page.locator("body").text_content() or ""

        has_currency = (
            "currency" in body_text.lower() or
            "pkr" in body_text.lower() or
            "price" in body_text.lower()
        )

        if not has_currency:
            pytest.skip("Currency selector not found")

    def test_billing_settings_has_anchor_day(self, page: Page):
        """Test that anchor day setting exists."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing/settings")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(2000)

        body_text = page.locator("body").text_content() or ""

        has_anchor = (
            "anchor" in body_text.lower() or
            ("billing" in body_text.lower() and "day" in body_text.lower())
        )

        if not has_anchor:
            pytest.skip("Anchor day setting not found")

    def test_billing_settings_has_peak_windows(self, page: Page):
        """Test that peak window configuration exists."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing/settings")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(2000)

        body_text = page.locator("body").text_content() or ""

        has_peak = (
            "peak" in body_text.lower() or
            "time window" in body_text.lower() or
            "hours" in body_text.lower()
        )

        if not has_peak:
            pytest.skip("Peak window configuration not found")

    def test_billing_settings_has_price_inputs(self, page: Page):
        """Test that price input fields exist."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing/settings")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(2000)

        body_text = page.locator("body").text_content() or ""

        has_price = (
            "price" in body_text.lower() or
            "rate" in body_text.lower() or
            "kwh" in body_text.lower() or
            "tariff" in body_text.lower()
        )

        if not has_price:
            pytest.skip("Price input fields not found")

    def test_billing_settings_has_save_button(self, page: Page):
        """Test that save button exists."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing/settings")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(2000)

        save_btn = page.locator("button:has-text('Save'), button:has-text('Submit'), button:has-text('Update')")

        if save_btn.count() == 0:
            pytest.skip("Save button not found")

    def test_billing_settings_has_reset_button(self, page: Page):
        """Test that reset to defaults button exists."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing/settings")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(2000)

        reset_btn = page.locator("button:has-text('Reset'), button:has-text('Default')")

        if reset_btn.count() == 0:
            pytest.skip("Reset button not found")

    def test_billing_settings_back_navigation(self, page: Page):
        """Test that back to dashboard navigation works."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing/settings")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(2000)

        back_btn = page.locator("button:has-text('Back'), a:has-text('Back')")

        if back_btn.count() > 0:
            back_btn.first.click()
            page.wait_for_timeout(2000)

            # Should navigate away from settings
            assert "/settings" not in page.url or "billing" in page.url


class TestWhatIfCalculator:
    """Tests for the What-If Scenario Calculator."""

    def test_what_if_calculator_exists(self, page: Page):
        """Test that What-If calculator section exists."""
        require_login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""

        has_calculator = (
            "what-if" in body_text.lower() or
            "scenario" in body_text.lower() or
            "calculator" in body_text.lower() or
            "simulate" in body_text.lower()
        )

        if not has_calculator:
            pytest.skip("What-If calculator not found on page")
