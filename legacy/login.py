import os
import sys
from playwright.sync_api import sync_playwright

def main():
    print("Starting Playwright interactive session...")
    
    with sync_playwright() as p:
        # Launch headed browser
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        
        # Create a new context
        context = browser.new_context()
        page = context.new_page()
        
        # Navigate to BPS FASIH
        print("Navigating to BPS FASIH...")
        page.goto("https://fasih-sm.bps.go.id/")
        
        print("\n" + "="*60)
        print("ACTION REQUIRED:")
        print("1. Please log in using your SSO account in the opened browser window.")
        print("2. Navigate to the survey page where the data table is displayed.")
        print("3. Once you are on the target page and see the table, return to this terminal.")
        print("4. Press ENTER here to save the session and continue.")
        print("="*60 + "\n")
        
        input("Press Enter here once you are on the target survey page...")
        
        # Save storage state
        auth_file = "auth_state.json"
        context.storage_state(path=auth_file)
        print(f"Session state successfully saved to '{auth_file}'")
        
        # Save target URL
        current_url = page.url
        url_file = "target_url.txt"
        with open(url_file, "w", encoding="utf-8") as f:
            f.write(current_url)
        print(f"Target survey URL saved to '{url_file}': {current_url}")
        
        browser.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error occurred: {e}", file=sys.stderr)
        input("Press Enter to exit...")
