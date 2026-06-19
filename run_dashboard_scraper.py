import os
import csv
import sys
import time
import re
from playwright.sync_api import sync_playwright

def get_active_pagination(page):
    pag_locators = page.locator("div:has-text('Menampilkan')")
    pag_count = pag_locators.count()
    for idx in range(pag_count):
        loc = pag_locators.nth(idx)
        if loc.is_visible():
            return loc
    return page.locator("div:has-text('Menampilkan')").last

def main():
    auth_file = "auth_state.json"
    target_url = "https://fasih-sm.bps.go.id/app/surveys/a0429e96-51a5-477b-a415-485f9c153004/fd68e454-ba45-4b85-8205-f3bf777ded24"
    output_csv = "dashboard_scraped_data.csv"
    
    # Status columns in the output CSV
    status_columns = [
        "OPEN", 
        "DRAFT", 
        "SUBMITTED BY Pencacah", 
        "REJECTED BY Pengawas", 
        "APPROVED BY Pengawas"
    ]
    
    headers = ["Category", "Email", "SLS Code"] + status_columns
    
    # Store aggregated records: (category, email, sls_code) -> dict of status counts
    scraped_data_dict = {}

    print("="*70)
    print("FASIH DASHBOARD SCRAPER EXPERIMENT")
    print("="*70)

    with sync_playwright() as p:
        print("Launching Chromium browser in headed mode...")
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        
        # Load saved session state if exists
        if os.path.exists(auth_file):
            print(f"Loading session from '{auth_file}'...")
            context = browser.new_context(storage_state=auth_file)
        else:
            print("No saved session state found. Creating new context.")
            context = browser.new_context()
            
        page = context.new_page()
        
        # Open BPS FASIH Dashboard
        print(f"Navigating to dashboard page: {target_url}")
        page.goto(target_url)
        
        # Check if we are on the target page and wait for load
        print("Waiting for page load and checking authentication...")
        start_time = time.time()
        authenticated = False
        while time.time() - start_time < 30.0:
            current_url = page.url
            if "sso" in current_url or "login" in current_url or "cas" in current_url or current_url.split('?')[0] != target_url.split('?')[0]:
                print("\n" + "="*80)
                print(f"NOT ON TARGET PAGE / REDIRECT DETECTED. Current URL: {current_url}")
                print(f"Please log in (if needed) and navigate to the target page: {target_url}")
                print("The scraper will automatically proceed once you reach the target page.")
                print("="*80 + "\n")
                
                # Wait indefinitely until we reach target url
                try:
                    page.wait_for_url(target_url, timeout=0)
                    print("Successfully reached the target page!")
                    # Save storage state immediately
                    context.storage_state(path=auth_file)
                    print(f"Session state saved to '{auth_file}'")
                    authenticated = True
                    break
                except KeyboardInterrupt:
                    print("Scraper aborted by user.")
                    browser.close()
                    return
            
            # Check if dashboard tabs are loaded
            if page.locator("button:has-text('Ringkasan')").count() > 0:
                print("Dashboard loaded successfully.")
                authenticated = True
                break
                
            page.wait_for_timeout(500)
            
        if not authenticated:
            print("Error: Could not load dashboard page. Aborting.")
            browser.close()
            return
            
        # 1. Download Ringkasan CSVs
        print("\n--- Phase 1: Downloading Ringkasan CSVs ---")
        # Click Ringkasan tab just in case
        page.locator("button:has-text('Ringkasan')").first.click()
        page.wait_for_timeout(1500)
        
        csv_buttons = page.locator("button:has(svg.tabler-icon-csv)")
        csv_count = csv_buttons.count()
        print(f"Found {csv_count} CSV buttons under Ringkasan tab.")
        
        for i in range(csv_count):
            label = "Assign" if i == 0 else "Progres"
            filename = f"ringkasan_{label}.csv"
            save_path = os.path.join("data", filename)
            print(f"  Downloading CSV #{i+1} ({label}) -> {save_path}...")
            try:
                with page.expect_download(timeout=15000) as download_info:
                    csv_buttons.nth(i).click()
                download = download_info.value
                download.save_as(save_path)
                print(f"  Saved to {save_path}")
            except Exception as e:
                print(f"  Failed to download CSV #{i+1}: {e}")
                
        # 2. Scrape Rekap Petugas (Pengawas & Pencacah)
        print("\n--- Phase 2: Scraping Rekap Petugas ---")
        page.locator("button:has-text('Rekap Petugas')").click()
        page.wait_for_timeout(2000)
        
        status_mapping = {
            "OPEN": "OPEN",
            "DRAFT": "DRAFT",
            "SUBMITTED BY PENCACAH": "SUBMITTED BY Pencacah",
            "REJECTED BY PENGAWAS": "REJECTED BY Pengawas",
            "APPROVED BY PENGAWAS": "APPROVED BY Pengawas",
        }
        
        last_first_email = None
        last_pag_text = None
        
        for category in ["Pengawas", "Pencacah"]:
            print(f"\nScraping Category: {category}")
            page.locator(f"button:has-text('{category}')").click()
            
            # Wait for tab transition to complete if switching categories
            if last_first_email is not None or last_pag_text is not None:
                print(f"  Waiting for tab transition from previous category...")
                start_transition = time.time()
                transitioned = False
                while time.time() - start_transition < 30.0:
                    page.wait_for_timeout(500)
                    cur_first_el = page.locator("button:has(div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm)").first
                    cur_first = cur_first_el.locator("div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm").text_content().strip() if cur_first_el.count() > 0 else ""
                    
                    cur_pag_el = get_active_pagination(page)
                    cur_pag = cur_pag_el.text_content().strip() if cur_pag_el and cur_pag_el.count() > 0 else ""
                    
                    if (cur_first != last_first_email or cur_pag != last_pag_text) and cur_first != "" and cur_pag != "":
                        transitioned = True
                        break
                if transitioned:
                    print("  Tab transition complete.")
                else:
                    print("  Warning: Tab transition timeout or no data.")
            else:
                # First category (Pengawas), just wait for cards to be visible
                print("  Waiting for initial cards to load...")
                try:
                    page.locator("button:has(div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm)").first.wait_for(state="visible", timeout=60000)
                except Exception:
                    print("  Warning: Timeout waiting for initial cards to load.")
                    
            page.wait_for_timeout(1000)
            
            # Force reset pagination to page 1 by clicking the "1" button if available
            page_one_btn = page.locator("a, button").filter(has_text=re.compile(r"^1$")).first
            if page_one_btn.count() > 0 and page_one_btn.is_visible():
                print("  Found Page 1 button, clicking to reset pagination...")
                page_one_btn.click()
                page.wait_for_timeout(2000)
                
            page_num = 1
            while True:
                # Get first email and pag text to detect page transitions
                first_email_el = page.locator("button:has(div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm)").first
                prev_first_email = None
                if first_email_el.count() > 0:
                    prev_first_email = first_email_el.locator("div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm").text_content().strip()
                
                prev_pag_el = get_active_pagination(page)
                prev_pag_text = prev_pag_el.text_content().strip() if prev_pag_el and prev_pag_el.count() > 0 else ""
                
                # Find all cards on this page
                cards_locator = page.locator("button:has(div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm)")
                card_count = cards_locator.count()
                print(f"  [Page {page_num}] Found {card_count} cards on current page.")
                
                for i in range(card_count):
                    card = cards_locator.nth(i)
                    email = card.locator("div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm").text_content().strip()
                    print(f"    [{i+1}/{card_count}] Scraped user: {email}")
                    
                    controls_id = card.get_attribute("aria-controls")
                    if not controls_id:
                        print("      Error: aria-controls attribute not found!")
                        continue
                        
                    content_panel = page.locator(f"#{controls_id}")
                    
                    # Expand card if collapsed
                    state = card.get_attribute("data-state")
                    if state != "open":
                        card.click()
                        
                    content_panel.wait_for(state="visible", timeout=10000)
                    
                    # Wait for SLS rows
                    try:
                        first_row = content_panel.locator("div.f\\:group.f\\:flex.f\\:flex-col.f\\:gap-3").first
                        first_row.wait_for(state="visible", timeout=10000)
                    except Exception:
                        print("      Timeout waiting for SLS rows.")
                        continue
                        
                    sls_rows = content_panel.locator("div.f\\:group.f\\:flex.f\\:flex-col.f\\:gap-3")
                    rows_count = sls_rows.count()
                    print(f"      Found {rows_count} SLS rows.")
                    
                    # Scrape SLS rows
                    for j in range(rows_count):
                        row = sls_rows.nth(j)
                        sls_code = row.locator("div.f\\:font-semibold.f\\:text-foreground.f\\:text-sm").text_content().strip()
                        tags = row.locator("div.f\\:flex.f\\:flex-wrap.f\\:items-center.f\\:gap-2 > div")
                        tags_count = tags.count()
                        
                        key = (category, email, sls_code)
                        if key not in scraped_data_dict:
                            scraped_data_dict[key] = {col: 0 for col in status_columns}
                            
                        for k in range(tags_count):
                            tag = tags.nth(k)
                            spans = tag.locator("span")
                            if spans.count() >= 2:
                                status_name = spans.nth(0).text_content().strip().upper()
                                count = spans.nth(1).text_content().strip()
                                if status_name in status_mapping:
                                    scraped_data_dict[key][status_mapping[status_name]] = int(count)
                                    
                    # Collapse card
                    card.click()
                    try:
                        content_panel.wait_for(state="hidden", timeout=5000)
                    except Exception:
                        pass
                        
                # Pagination: Go to next page
                pagination_container = get_active_pagination(page)
                next_btn = None
                if pagination_container:
                    next_btn = pagination_container.locator("a:has-text('Next'), button:has-text('Next')").first
                
                is_disabled = False
                if next_btn and next_btn.count() > 0:
                    btn_class = next_btn.get_attribute("class") or ""
                    btn_disabled = next_btn.get_attribute("disabled")
                    aria_disabled = next_btn.get_attribute("aria-disabled")
                    data_disabled = next_btn.get_attribute("data-disabled")
                    
                    classes = btn_class.split()
                    is_pointer_events_none = False
                    is_opacity_50 = False
                    has_disabled_class = False
                    for cls in classes:
                        if 'pointer-events-none' in cls and 'disabled:' not in cls:
                            is_pointer_events_none = True
                        if 'opacity-50' in cls and 'disabled:' not in cls:
                            is_opacity_50 = True
                        if cls == 'disabled' or cls == 'f:disabled' or 'btn-disabled' in cls:
                            has_disabled_class = True
                    
                    if (is_pointer_events_none or 
                        is_opacity_50 or 
                        has_disabled_class or 
                        aria_disabled == 'true' or 
                        data_disabled == 'true' or 
                        data_disabled == '' or 
                        btn_disabled is not None):
                        is_disabled = True
                        
                if next_btn and next_btn.count() > 0 and next_btn.is_visible() and not is_disabled and prev_first_email:
                    # Click next with retry
                    clicked_ok = False
                    for attempt in range(3):
                        if attempt > 0:
                            print(f"  Retrying next page click (attempt {attempt+1}/3)...")
                        
                        try:
                            # Use a longer timeout (45s) for slow page transitions
                            next_btn.click(timeout=45000)
                        except Exception as e:
                            print(f"  Click Next button failed or timed out (expected if disabled/last page): {e}")
                            break
                        
                        # Wait for page transition
                        start_time = time.time()
                        page_changed = False
                        while time.time() - start_time < 45.0:
                            page.wait_for_timeout(500)
                            
                            # Check first email
                            current_first_email_el = page.locator("button:has(div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm)").first
                            current_first_email = ""
                            if current_first_email_el.count() > 0:
                                current_first_email = current_first_email_el.locator("div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm").text_content().strip()
                                
                            # Check pagination text
                            cur_pag_el = get_active_pagination(page)
                            current_pag_text = cur_pag_el.text_content().strip() if cur_pag_el and cur_pag_el.count() > 0 else ""
                            
                            if (current_first_email != prev_first_email and current_first_email != "") or (current_pag_text != prev_pag_text and current_pag_text != ""):
                                page_changed = True
                                break
                                
                        if page_changed:
                            clicked_ok = True
                            break
                            
                    if not clicked_ok:
                        print("  Warning: Pagination transition timeout after retries. Breaking pagination loop.")
                        break
                        
                    page_num += 1
                    page.wait_for_timeout(1000)
                else:
                    print("  Reached the last page.")
                    break
            
            # Save the last first email and pagination text for the next tab's transition check
            last_first_el = page.locator("button:has(div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm)").first
            last_first_email = last_first_el.locator("div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm").text_content().strip() if last_first_el.count() > 0 else ""
            
            last_pag_el = get_active_pagination(page)
            last_pag_text = last_pag_el.text_content().strip() if last_pag_el and last_pag_el.count() > 0 else ""
                    
        # 3. Export to pivoted CSV
        print(f"\n--- Phase 3: Exporting pivoted data to '{output_csv}' ---")
        try:
            with open(output_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                
                for key, val in scraped_data_dict.items():
                    row = list(key) + [val[col] for col in status_columns]
                    writer.writerow(row)
                    
            print(f"Successfully scraped and written {len(scraped_data_dict)} SLS status rows to '{output_csv}'!")
        except Exception as csv_err:
            print(f"Error writing output CSV: {csv_err}")
            
        browser.close()

if __name__ == "__main__":
    main()
