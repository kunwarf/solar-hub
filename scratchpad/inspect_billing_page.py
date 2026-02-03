"""
Playwright script to inspect the billing page.
Logs in with production credentials, navigates to the billing page,
and captures API responses, console logs, and screenshots.
"""
import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright, Page

# Configuration
LOGIN_URL = "http://182.180.150.107:8050/auth"
BILLING_URL = "http://182.180.150.107:8050/billing?site_id=271edc3f-f8e8-4aac-acae-78ffd8bf4643"
EMAIL = "kunwar.faisal@gmail.com"
PASSWORD = "Test@123"

# Storage for API responses and console logs
api_responses = {}
console_logs = []


def save_report(data: dict, filename: str):
    """Save report data to JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Report saved to: {filename}")


async def setup_listeners(page: Page):
    """Setup listeners for console logs and network requests."""

    # Console listener
    def handle_console(msg):
        log_entry = {
            "type": msg.type,
            "text": msg.text,
            "location": msg.location
        }
        console_logs.append(log_entry)
        print(f"[CONSOLE {msg.type.upper()}] {msg.text}")

    page.on("console", handle_console)

    # Network listener for API responses
    async def handle_response(response):
        url = response.url

        # Log all API calls for debugging
        if "/api/v1/" in url:
            print(f"[API] {response.request.method} {url} - Status: {response.status}")

        # Track specific API endpoints
        if "/api/v1/billing/running-bill" in url:
            try:
                body = await response.json()
                api_responses["running_bill"] = {
                    "url": url,
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": body
                }
                print(f"[API] Captured /api/v1/billing/running-bill response")
            except Exception as e:
                api_responses["running_bill"] = {
                    "url": url,
                    "status": response.status,
                    "error": str(e)
                }

        elif "/api/v1/dashboard/widgets/all" in url:
            try:
                body = await response.json()
                api_responses["widgets_all"] = {
                    "url": url,
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": body
                }
                print(f"[API] Captured /api/v1/dashboard/widgets/all response")
            except Exception as e:
                api_responses["widgets_all"] = {
                    "url": url,
                    "status": response.status,
                    "error": str(e)
                }

        elif "/api/v1/dashboard/energy-chart" in url:
            try:
                body = await response.json()
                api_responses["energy_chart"] = {
                    "url": url,
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": body
                }
                print(f"[API] Captured /api/v1/dashboard/energy-chart response")
            except Exception as e:
                api_responses["energy_chart"] = {
                    "url": url,
                    "status": response.status,
                    "error": str(e)
                }

    page.on("response", handle_response)


async def login(page: Page):
    """Login to the application."""
    print(f"Navigating to login page: {LOGIN_URL}")
    await page.goto(LOGIN_URL, wait_until="networkidle")

    # Wait for login form
    await page.wait_for_selector('input[type="email"], input[name="email"]', timeout=10000)

    # Fill in credentials
    print("Filling in login credentials...")
    await page.fill('input[type="email"], input[name="email"]', EMAIL)
    await page.fill('input[type="password"], input[name="password"]', PASSWORD)

    # Click login button and wait for navigation
    print("Clicking login button...")
    async with page.expect_navigation(timeout=30000):
        await page.click('button[type="submit"]')

    # Wait for page to fully load after navigation
    await page.wait_for_load_state("networkidle")
    print(f"Login completed. Current URL: {page.url}")

    # Additional wait to ensure authentication token is set
    await page.wait_for_timeout(2000)


async def extract_displayed_values(page: Page) -> dict:
    """Extract the displayed values from the billing page."""
    print("\nExtracting displayed values from the page...")

    displayed_values = {}

    # First, let's get all the text content from the page
    page_content = await page.content()
    all_text = await page.evaluate("() => document.body.innerText")

    # Save all text to report for debugging
    displayed_values["_raw_page_text"] = all_text

    try:
        print(f"\n--- PAGE TEXT CONTENT (first 1000 chars) ---")
        # Use encode with error handling for printing
        print(all_text[:1000].encode('utf-8', errors='replace').decode('utf-8'))
        print("--- END PAGE TEXT ---\n")
    except Exception as e:
        print(f"Could not print page text: {e}")

    # Common selectors to try for each metric
    metrics = [
        "Energy Produced",
        "Energy Consumed",
        "Grid Earnings",
        "Grid Costs",
        "Net Balance",
        "Estimated Monthly Savings"
    ]

    for metric in metrics:
        try:
            # Try multiple selector strategies
            value = None

            # Strategy 1: Look for text containing the metric name, then find nearby value
            try:
                # Find element containing the metric text
                elements = await page.locator(f'text="{metric}"').all()
                if elements:
                    # Get parent and look for numbers
                    parent = await elements[0].locator('..').inner_text()
                    # Try to extract number from parent text
                    import re
                    numbers = re.findall(r'[\d,]+\.?\d*', parent)
                    if numbers:
                        value = numbers[-1]  # Usually the last number is the value
            except Exception as e:
                print(f"  Strategy 1 failed for {metric}: {str(e)}")

            # Strategy 2: Use a more flexible text search
            if not value:
                try:
                    # Search in all text for pattern "Metric: Value" or "Metric Value"
                    import re
                    pattern = rf'{metric}[:\s]+([0-9,]+\.?[0-9]*)'
                    matches = re.findall(pattern, all_text, re.IGNORECASE)
                    if matches:
                        value = matches[0]
                except Exception as e:
                    print(f"  Strategy 2 failed for {metric}: {str(e)}")

            # If still no value found
            if not value:
                value = "Not found on page"

            displayed_values[metric] = value
            print(f"  {metric}: {value}")

        except Exception as e:
            displayed_values[metric] = f"Error: {str(e)}"
            print(f"  {metric}: Error - {str(e)}")

    return displayed_values


async def main():
    """Main execution function."""
    print("=" * 80)
    print("BILLING PAGE INSPECTION SCRIPT")
    print("=" * 80)

    async with async_playwright() as p:
        # Launch browser
        print("\nLaunching browser...")
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        # Setup listeners
        await setup_listeners(page)

        try:
            # Login
            await login(page)

            # Navigate to billing page
            print(f"\nNavigating to billing page: {BILLING_URL}")
            await page.goto(BILLING_URL, wait_until="networkidle")

            # Wait a bit for dynamic content to load
            print("Waiting for page to fully load...")
            await page.wait_for_timeout(3000)

            # Try to wait for specific billing elements (with timeout)
            try:
                await page.wait_for_selector('text=Energy Produced', timeout=5000)
                print("Billing content detected on page")
            except:
                print("Note: Could not find 'Energy Produced' text, page might still be loading or use different labels")

            # Wait a bit more for any API calls to complete
            await page.wait_for_timeout(3000)

            # Extract displayed values
            displayed_values = await extract_displayed_values(page)

            # Take screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"C:\\Users\\kunwa\\PycharmProjects\\solar-hub\\scratchpad\\billing_page_{timestamp}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"\nScreenshot saved to: {screenshot_path}")

            # Wait a bit more to ensure all API calls complete
            await page.wait_for_timeout(2000)

            # Compile report
            report = {
                "timestamp": datetime.now().isoformat(),
                "url": BILLING_URL,
                "displayed_values": displayed_values,
                "api_responses": api_responses,
                "console_logs": console_logs,
                "screenshot_path": screenshot_path
            }

            # Save report
            report_path = f"C:\\Users\\kunwa\\PycharmProjects\\solar-hub\\scratchpad\\billing_inspection_report_{timestamp}.json"
            save_report(report, report_path)

            # Print summary
            print("\n" + "=" * 80)
            print("INSPECTION SUMMARY")
            print("=" * 80)

            print("\n1. DISPLAYED VALUES:")
            for key, value in displayed_values.items():
                print(f"   {key}: {value}")

            print("\n2. API RESPONSES CAPTURED:")
            for api_name, api_data in api_responses.items():
                print(f"   {api_name}: Status {api_data.get('status', 'N/A')}")

            print("\n3. CONSOLE ERRORS:")
            errors = [log for log in console_logs if log['type'] == 'error']
            if errors:
                for error in errors:
                    print(f"   {error['text']}")
            else:
                print("   No console errors detected")

            print("\n4. FILES GENERATED:")
            print(f"   Screenshot: {screenshot_path}")
            print(f"   Report: {report_path}")

            print("\n" + "=" * 80)

        except Exception as e:
            print(f"\nError during execution: {str(e)}")
            import traceback
            traceback.print_exc()

        finally:
            # Keep browser open for a moment
            print("\nKeeping browser open for 5 seconds...")
            await page.wait_for_timeout(5000)
            await browser.close()
            print("Browser closed.")


if __name__ == "__main__":
    asyncio.run(main())
