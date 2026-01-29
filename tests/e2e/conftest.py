"""
Pytest configuration for E2E tests with Playwright.
"""
import pytest
from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page


@pytest.fixture(scope="session")
def playwright():
    """Provide Playwright instance."""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Browser:
    """Launch browser once per test session."""
    browser = playwright.chromium.launch(
        headless=True,  # Set to False to see the browser
        slow_mo=100,    # Slow down actions by 100ms for visibility
    )
    yield browser
    browser.close()


@pytest.fixture(scope="function")
def context(browser: Browser) -> BrowserContext:
    """Create a new browser context for each test."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Page:
    """Create a new page for each test."""
    page = context.new_page()
    yield page
    page.close()
