"""
Enhanced Playwright script to specifically capture billing API responses.
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

# Storage for API responses
api_responses = {}


async def setup_listeners(page: Page):
    """Setup listeners for API responses."""

    async def handle_response(response):
        url = response.url

        # Capture all billing-related API endpoints
        if "/api/v1/billing/" in url or "/api/v1/dashboard/" in url:
            try:
                body = await response.json()
                endpoint_key = url.split("/api/v1/")[-1].split("?")[0]  # Extract endpoint name
                api_responses[url] = {
                    "endpoint": endpoint_key,
                    "url": url,
                    "status": response.status,
                    "body": body
                }
                print(f"[CAPTURED] {endpoint_key} - Status: {response.status}")
            except Exception as e:
                print(f"[ERROR] Could not parse response from {url}: {e}")

    page.on("response", handle_response)


async def login(page: Page):
    """Login to the application."""
    print(f"Navigating to login page: {LOGIN_URL}")
    await page.goto(LOGIN_URL, wait_until="networkidle")
    await page.wait_for_selector('input[type="email"], input[name="email"]', timeout=10000)

    print("Logging in...")
    await page.fill('input[type="email"], input[name="email"]', EMAIL)
    await page.fill('input[type="password"], input[name="password"]', PASSWORD)

    async with page.expect_navigation(timeout=30000):
        await page.click('button[type="submit"]')

    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2000)
    print(f"Login successful. Current URL: {page.url}")


async def main():
    """Main execution function."""
    print("=" * 80)
    print("BILLING API CAPTURE SCRIPT")
    print("=" * 80)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()

        await setup_listeners(page)

        try:
            # Login
            await login(page)

            # Navigate to billing page
            print(f"\nNavigating to billing page: {BILLING_URL}")
            await page.goto(BILLING_URL, wait_until="networkidle")

            # Wait for billing content to load
            print("Waiting for billing data to load...")
            await page.wait_for_timeout(5000)

            # Try to wait for specific billing elements
            try:
                await page.wait_for_selector('text=Energy Produced', timeout=5000)
            except:
                pass

            # Additional wait to ensure all API calls complete
            await page.wait_for_timeout(3000)

            # Save captured responses
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = f"C:\\Users\\kunwa\\PycharmProjects\\solar-hub\\scratchpad\\billing_api_capture_{timestamp}.json"

            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(api_responses, f, indent=2, ensure_ascii=False)

            print(f"\n{'=' * 80}")
            print("CAPTURED API ENDPOINTS:")
            print(f"{'=' * 80}\n")

            for url, data in api_responses.items():
                print(f"Endpoint: {data['endpoint']}")
                print(f"URL: {url}")
                print(f"Status: {data['status']}")
                print(f"Body preview: {str(data['body'])[:200]}...")
                print("-" * 80)

            print(f"\nFull report saved to: {report_path}")
            print(f"Total APIs captured: {len(api_responses)}")

        except Exception as e:
            print(f"\nError during execution: {str(e)}")
            import traceback
            traceback.print_exc()

        finally:
            print("\nKeeping browser open for 5 seconds...")
            await page.wait_for_timeout(5000)
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
