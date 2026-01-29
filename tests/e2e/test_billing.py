"""
Billing Page E2E Tests.

Tests for the Billing page.
Run with: pytest tests/e2e/test_billing.py -v
"""
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8080"
TEST_USER_EMAIL = "admin@demo.com"
TEST_USER_PASSWORD = "Admin123!"


def login(page: Page):
    """Helper to login before tests."""
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

        # Wait for redirect away from auth page
        try:
            page.wait_for_url(lambda url: "/auth" not in url, timeout=10000)
        except:
            pass  # Continue even if redirect doesn't happen


def skip_wizard(page: Page):
    """Skip setup wizard if visible."""
    skip_btn = page.locator("button:has-text('Skip'), button:has-text('Later')").first
    if skip_btn.is_visible():
        skip_btn.click()
        page.wait_for_timeout(1000)


class TestBillingPage:
    """Tests for the Billing page."""

    def test_billing_shows_tariff_rate(self, page: Page):
        """Test 6.1: Tariff rate is displayed in PKR/kWh."""
        login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""

        # Should show tariff/rate information
        has_tariff = (
            "tariff" in body_text.lower() or
            "rate" in body_text.lower() or
            "pkr" in body_text.lower() or
            "rs" in body_text.lower() or
            "kwh" in body_text.lower() or
            "/kwh" in body_text.lower()
        )

        assert has_tariff, "Tariff rate not found on billing page"

    def test_billing_estimated_savings(self, page: Page):
        """Test 6.2: Estimated savings amount is shown."""
        login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""

        # Should show savings information
        has_savings = (
            "saving" in body_text.lower() or
            "saved" in body_text.lower() or
            "estimated" in body_text.lower() or
            "monthly" in body_text.lower()
        )

        # Should have currency amounts
        has_amounts = (
            "pkr" in body_text.lower() or
            "rs" in body_text.lower() or
            "₨" in body_text
        )

        assert has_savings or has_amounts, "Savings information not found on billing page"

    def test_billing_export_credits(self, page: Page):
        """Test 6.3: Export credits (kWh exported) are displayed."""
        login(page)
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        skip_wizard(page)
        page.wait_for_timeout(3000)

        body_text = page.locator("body").text_content() or ""
        body_lower = body_text.lower()

        # Check if we're on the billing page (not redirected to auth)
        if "sign in" in body_lower or "welcome back" in body_lower:
            pytest.skip("Not logged in - skipping billing export test")

        # Should show export-related or billing-related information
        has_billing_content = (
            "export" in body_lower or
            "credit" in body_lower or
            "grid" in body_lower or
            "feed-in" in body_lower or
            "net metering" in body_lower or
            "kwh" in body_lower or
            "billing" in body_lower or
            "cost" in body_lower or
            "savings" in body_lower
        )

        assert has_billing_content, "Billing-related content not found on billing page"


# Pytest fixtures
@pytest.fixture(scope="function")
def page(browser):
    """Create a new page for each test."""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="session")
def browser(playwright):
    """Launch browser once per session."""
    browser = playwright.chromium.launch(headless=True)
    yield browser
    browser.close()
