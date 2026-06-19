import os
import re
import csv
import sys
import time
import json
import webbrowser
from playwright.sync_api import sync_playwright
import process_data

def load_env(env_path=".env"):
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip()
                        # Strip optional quotes
                        if val.startswith('"') and val.endswith('"'):
                            val = val[1:-1]
                        elif val.startswith("'") and val.endswith("'"):
                            val = val[1:-1]
                        env_vars[key] = val
    return env_vars

def load_emails(file_path):
    if not os.path.exists(file_path):
        print(f"Error: Email list file '{file_path}' not found.")
        sys.exit(1)
    with open(file_path, "r", encoding="utf-8") as f:
        emails = [line.strip() for line in f if line.strip()]
    return emails

def get_active_pagination(page):
    pag_locators = page.locator("div:has-text('Menampilkan')")
    pag_count = pag_locators.count()
    for idx in range(pag_count):
        loc = pag_locators.nth(idx)
        if loc.is_visible():
            return loc
    return page.locator("div:has-text('Menampilkan')").last

def wait_for_table_load(page, searched_text=None, previous_first_row_text=None, timeout=45000):
    start_time = time.time()
    page.wait_for_timeout(500)
    
    try:
        loaders = page.locator("svg.tabler-icon-loader, svg.tabler-icon-loader-2")
        if loaders.count() > 0:
            loaders.first.wait_for(state="hidden", timeout=timeout)
    except Exception:
        pass

    while time.time() - start_time < (timeout / 1000.0):
        rows = page.locator("table tbody tr")
        row_count = rows.count()
        
        if row_count > 0:
            first_row_text = rows.first.text_content()
            first_row_text_lower = first_row_text.lower()
            is_no_data = "tidak ada data" in first_row_text_lower or "empty" in first_row_text_lower or "no data" in first_row_text_lower
            
            if previous_first_row_text is not None:
                if first_row_text != previous_first_row_text:
                    break
            elif searched_text is not None:
                if is_no_data:
                    break
                tbody_text = page.locator("table tbody").text_content().lower()
                if searched_text.lower() in tbody_text:
                    break
            else:
                break
        time.sleep(0.5)
    time.sleep(1.0)

def scrape_page(page, searched_email, csv_writer):
    rows_locator = page.locator("table tbody tr")
    row_count = rows_locator.count()
    
    if row_count == 0:
        print(f"  No rows found in table.")
        return 0
        
    first_row_text = rows_locator.first.text_content().lower()
    if "tidak ada data" in first_row_text or "empty" in first_row_text or "no data" in first_row_text:
        print(f"  No data matching search.")
        return 0
        
    scraped_count = 0
    for i in range(row_count):
        cols = rows_locator.nth(i).locator("td").all_text_contents()
        if len(cols) >= 16:
            cleaned_cols = [c.strip() for c in cols]
            csv_writer.writerow([searched_email] + cleaned_cols[1:16])
            scraped_count += 1
            
    print(f"  Scraped {scraped_count} rows from current page.")
    return scraped_count

def run_unified_scraper():
    use_test = "--test" in sys.argv
    email_file = os.path.join("data", "email_mitra_test.txt" if use_test else "email_mitra.txt")
    auth_file = "auth_state.json"
    dashboard_csv = "dashboard_scraped_data.csv"
    output_csv = "scraped_data.csv"
    checkpoint_file = "checkpoint.json"
    
    # 1. Load configuration and emails
    env = load_env()
    username = env.get("USERNAME")
    password = env.get("PASSWORD")
    
    if not username or not password:
        print("Error: USERNAME or PASSWORD not set in .env file.")
        sys.exit(1)
        
    # Check execution mode (full, dashboard, data)
    run_mode = "full"
    if "--dashboard" in sys.argv:
        run_mode = "dashboard"
        print("Run mode: DASHBOARD ONLY")
    elif "--data" in sys.argv or "--scrape" in sys.argv or "--ambil-data" in sys.argv:
        run_mode = "data"
        print("Run mode: AMBIL DATA ONLY")
    elif "--full" in sys.argv:
        run_mode = "full"
        print("Run mode: FULL (Dashboard + Ambil Data)")
    else:
        print("\nPilih mode eksekusi:")
        print("  1. Run Full (Dashboard & Ambil Data - default)")
        print("  2. Run Dashboard Saja")
        print("  3. Run Ambil Data Saja")
        try:
            choice = input("Masukkan pilihan (1/2/3) [1]: ").strip()
            if choice == "2":
                run_mode = "dashboard"
                print("Run mode: DASHBOARD ONLY")
            elif choice == "3":
                run_mode = "data"
                print("Run mode: AMBIL DATA ONLY")
            else:
                run_mode = "full"
                print("Run mode: FULL (Dashboard + Ambil Data)")
        except (KeyboardInterrupt, SystemExit):
            print("\nExiting script.")
            sys.exit(0)
        except Exception:
            print("Invalid input, defaulting to: FULL (Dashboard + Ambil Data).")
            run_mode = "full"

    emails = []
    reverse_order = False
    resume_index = 0

    if run_mode in ["full", "data"]:
        emails = load_emails(email_file)
        
        # Check scraping order
        if "--bottom" in sys.argv or "--reverse" in sys.argv:
            reverse_order = True
            print("Scraping order: BOTTOM TO TOP (Reversed).")
        elif "--top" in sys.argv:
            reverse_order = False
            print("Scraping order: TOP TO BOTTOM (Normal).")
        else:
            print("\nPilih urutan scraping detail email:")
            print("  1. Dari Atas ke Bawah (Normal - default)")
            print("  2. Dari Bawah ke Atas (Terbalik/Reverse)")
            try:
                choice = input("Masukkan pilihan (1/2) [1]: ").strip()
                if choice == "2":
                    reverse_order = True
                    print("Order: BOTTOM TO TOP (Reversed).")
                else:
                    print("Order: TOP TO BOTTOM (Normal).")
            except (KeyboardInterrupt, SystemExit):
                print("\nExiting script.")
                sys.exit(0)
            except Exception:
                print("Invalid input, defaulting to: TOP TO BOTTOM (Normal).")
                
        if reverse_order:
            emails.reverse()
            
        # Check checkpoint for detail scraping
        use_fresh = "--fresh" in sys.argv
        if not use_fresh and os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, "r") as f:
                    cp = json.load(f)
                    last_email = cp.get("last_email")
                    if last_email and last_email in emails:
                        resume_index = emails.index(last_email) + 1
                        print(f"Resuming from checkpoint at email #{resume_index + 1} ({emails[resume_index]})")
            except Exception as e:
                print(f"Warning reading checkpoint: {e}. Starting fresh.")

    # Status columns in the output CSV for dashboard
    status_columns = [
        "OPEN", 
        "DRAFT", 
        "SUBMITTED BY Pencacah", 
        "REJECTED BY Pengawas", 
        "APPROVED BY Pengawas"
    ]
    dashboard_headers = ["Category", "Email", "SLS Code"] + status_columns
    scraped_data_dict = {}

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
        
        # 2. Automated Login via SSO
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"Navigating to BPS FASIH website (Attempt {attempt}/{max_attempts})...")
                page.goto("https://fasih-sm.bps.go.id/", timeout=120000)
                break
            except Exception as e:
                print(f"Error navigating to BPS FASIH website: {e}")
                if attempt == max_attempts:
                    raise
                wait_sec = attempt * 10
                print(f"Waiting {wait_sec} seconds before retrying...")
                page.wait_for_timeout(wait_sec * 1000)
        page.wait_for_timeout(3000)
        
        # Check if we need to log in
        if "sso.bps.go.id" in page.url or page.locator("#username").count() > 0 or page.locator("text=Login SSO BPS").count() > 0:
            print("Login SSO required.")
            if page.locator("text=Login SSO BPS").count() > 0:
                print("Clicking 'Login SSO BPS'...")
                page.locator("text=Login SSO BPS").first.click()
                page.wait_for_timeout(3000)
                
            if page.locator("#username").count() > 0:
                print(f"Filling credentials for user: {username}...")
                page.locator("#username").fill(username)
                page.locator("#password").fill(password)
                page.locator("#kc-login").click()
                page.wait_for_timeout(5000)
                
        # Wait for redirect to /app
        try:
            page.wait_for_url("**/app**", timeout=45000)
            print("Successfully reached the app workspace!")
        except Exception:
            print("Warning: Redirection timeout. Checking current URL: " + page.url)
            
        # Save session immediately
        context.storage_state(path=auth_file)
        print(f"Session state saved to '{auth_file}'")
        
        # 3. Search and select survey
        print("Searching for 'SENSUS EKONOMI 2026'...")
        if not page.url.endswith("/app") and "/app/surveys" not in page.url:
            page.goto("https://fasih-sm.bps.go.id/app")
            page.wait_for_timeout(2000)
            
        search_input = page.locator('input[placeholder="Cari survei..."]')
        search_input.wait_for(state="visible", timeout=30000)
        search_input.fill("SENSUS EKONOMI 2026")
        search_input.press("Enter")
        page.wait_for_timeout(2500)
        
        # Click the row with exact text "SENSUS EKONOMI 2026"
        print("Finding exact match for 'SENSUS EKONOMI 2026'...")
        survey_items = page.locator("text=SENSUS EKONOMI 2026")
        survey_items.first.wait_for(state="visible", timeout=30000)
        
        survey_item = None
        count = survey_items.count()
        for idx in range(count):
            item = survey_items.nth(idx)
            txt = item.text_content().strip()
            if txt == "SENSUS EKONOMI 2026":
                survey_item = item
                break
                
        if survey_item is None:
            print("Exact match 'SENSUS EKONOMI 2026' not found by scanning text. Trying get_by_text exact match...")
            try:
                exact_loc = page.get_by_text("SENSUS EKONOMI 2026", exact=True).first
                if exact_loc.count() > 0:
                    survey_item = exact_loc
            except Exception:
                pass
                
        if survey_item is None:
            print("Warning: Exact match 'SENSUS EKONOMI 2026' not found, falling back to first partial match.")
            survey_item = page.locator("text=SENSUS EKONOMI 2026").first
            
        print(f"Clicking survey item: '{survey_item.text_content().strip()}'")
        survey_item.click()
        page.wait_for_timeout(3000)
        
        # Click the "PENDATAAN" card/button to enter dashboard
        print("Navigating to PENDATAAN period...")
        pendataan_btn = page.locator("text=PENDATAAN").first
        pendataan_btn.wait_for(state="visible", timeout=30000)
        pendataan_btn.click()
        page.wait_for_timeout(3000)
        
        if run_mode in ["full", "dashboard"]:
            # 4. Scrape Dashboard Rekap Data
            print("\n--- Phase 1: Downloading Ringkasan CSVs ---")
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
                    print("  Waiting for initial cards to load...")
                    try:
                        page.locator("button:has(div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm)").first.wait_for(state="visible", timeout=60000)
                    except Exception:
                        print("  Warning: Timeout waiting for initial cards to load.")
                        
                page.wait_for_timeout(1000)
                
                page_one_btn = page.locator("a, button").filter(has_text=re.compile(r"^1$")).first
                if page_one_btn.count() > 0 and page_one_btn.is_visible():
                    print("  Found Page 1 button, clicking to reset pagination...")
                    page_one_btn.click()
                    page.wait_for_timeout(2000)
                    
                page_num = 1
                while True:
                    first_email_el = page.locator("button:has(div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm)").first
                    prev_first_email = None
                    if first_email_el.count() > 0:
                        prev_first_email = first_email_el.locator("div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm").text_content().strip()
                    
                    prev_pag_el = get_active_pagination(page)
                    prev_pag_text = prev_pag_el.text_content().strip() if prev_pag_el and prev_pag_el.count() > 0 else ""
                    
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
                        state = card.get_attribute("data-state")
                        if state != "open":
                            card.click()
                            
                        content_panel.wait_for(state="visible", timeout=10000)
                        
                        try:
                            first_row = content_panel.locator("div.f\\:group.f\\:flex.f\\:flex-col.f\\:gap-3").first
                            first_row.wait_for(state="visible", timeout=10000)
                        except Exception:
                            print("      Timeout waiting for SLS rows.")
                            continue
                            
                        sls_rows = content_panel.locator("div.f\\:group.f\\:flex.f\\:flex-col.f\\:gap-3")
                        rows_count = sls_rows.count()
                        print(f"      Found {rows_count} SLS rows.")
                        
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
                                        
                        card.click()
                        try:
                            content_panel.wait_for(state="hidden", timeout=5000)
                        except Exception:
                            pass
                            
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
                        
                        if (is_pointer_events_none or is_opacity_50 or has_disabled_class or 
                            aria_disabled == 'true' or data_disabled == 'true' or data_disabled == '' or 
                            btn_disabled is not None):
                            is_disabled = True
                            
                    if next_btn and next_btn.count() > 0 and next_btn.is_visible() and not is_disabled and prev_first_email:
                        clicked_ok = False
                        for attempt in range(3):
                            if attempt > 0:
                                print(f"  Retrying next page click (attempt {attempt+1}/3)...")
                            
                            try:
                                next_btn.click(timeout=45000)
                            except Exception as e:
                                print(f"  Click Next button failed or timed out: {e}")
                                break
                            
                            start_time = time.time()
                            page_changed = False
                            while time.time() - start_time < 45.0:
                                page.wait_for_timeout(500)
                                current_first_email_el = page.locator("button:has(div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm)").first
                                current_first_email = ""
                                if current_first_email_el.count() > 0:
                                    current_first_email = current_first_email_el.locator("div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm").text_content().strip()
                                    
                                cur_pag_el = get_active_pagination(page)
                                current_pag_text = cur_pag_el.text_content().strip() if cur_pag_el and cur_pag_el.count() > 0 else ""
                                
                                if (current_first_email != prev_first_email and current_first_email != "") or (current_pag_text != prev_pag_text and current_pag_text != ""):
                                    page_changed = True
                                    break
                                    
                            if page_changed:
                                clicked_ok = True
                                break
                                
                        if not clicked_ok:
                            print("  Warning: Pagination transition timeout. Breaking loop.")
                            break
                            
                        page_num += 1
                        page.wait_for_timeout(1000)
                    else:
                        print("  Reached last page of category.")
                        break
                
                last_first_el = page.locator("button:has(div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm)").first
                last_first_email = last_first_el.locator("div.f\\:m-0.f\\:truncate.f\\:font-semibold.f\\:text-sm").text_content().strip() if last_first_el.count() > 0 else ""
                last_pag_el = get_active_pagination(page)
                last_pag_text = last_pag_el.text_content().strip() if last_pag_el and last_pag_el.count() > 0 else ""
     
            # Export dashboard CSV
            print(f"\nWriting dashboard data to '{dashboard_csv}'...")
            try:
                with open(dashboard_csv, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(dashboard_headers)
                    for key, val in scraped_data_dict.items():
                        row = list(key) + [val[col] for col in status_columns]
                        writer.writerow(row)
                print(f"Successfully scraped and written {len(scraped_data_dict)} SLS status rows to '{dashboard_csv}'!")
            except Exception as csv_err:
                print(f"Error writing dashboard CSV: {csv_err}")
     
            # 5. Intermediate processing and Git push
            print("\nProcessing intermediate dashboard data...")
            try:
                import process_data
                process_data.process_dashboard_scraped_data()
                
                # Copy dashboard_scraped_data.csv to public folder
                public_dir = os.path.join("dashboard", "public")
                if os.path.exists(public_dir):
                    import shutil
                    shutil.copy2(dashboard_csv, os.path.join(public_dir, "dashboard_scraped_data.csv"))
                    
                    # Copy other files
                    pml_ppl_src = os.path.join("data", "pml_ppl.csv")
                    if os.path.exists(pml_ppl_src):
                        shutil.copy2(pml_ppl_src, os.path.join(public_dir, "pml_ppl.csv"))
                    
                    assign_src = os.path.join("data", "ringkasan_Assign.csv")
                    if os.path.exists(assign_src):
                        shutil.copy2(assign_src, os.path.join(public_dir, "ringkasan_Assign.csv"))
                    
                    progres_src = os.path.join("data", "ringkasan_Progres.csv")
                    if os.path.exists(progres_src):
                        shutil.copy2(progres_src, os.path.join(public_dir, "ringkasan_Progres.csv"))
                    
                    # Write timestamp
                    timestamp = process_data.get_wita_timestamp()
                    with open(os.path.join(public_dir, "last_updated.txt"), "w", encoding="utf-8") as tf:
                        tf.write(timestamp)
                    
                    # Git push is removed as per user request
                    pass
            except Exception as proc_err:
                print(f"Warning during intermediate processing: {proc_err}")

        if run_mode in ["full", "data"]:
            # 6. Navigate to detail "Data" tab
            print("\n--- Phase 3: Transitioning to Detail Data Tab ---")
            
            # Try to click the Data tab in the sidebar first
            data_menu = None
            selectors = [
                "a[href$='/data']",
                "a[href*='/data']",
                "a:has-text('Data')"
            ]
            
            for selector in selectors:
                loc = page.locator(selector)
                if loc.count() > 0:
                    try:
                        loc.first.wait_for(state="visible", timeout=3000)
                        data_menu = loc.first
                        print(f"  Found Data tab using selector: '{selector}'")
                        break
                    except Exception:
                        continue
                        
            if data_menu:
                data_menu.click()
                page.wait_for_timeout(3000)
                
            # Verify if we are on the data page. If not, construct and navigate directly
            current_url = page.url
            base_url = current_url.split("?")[0]
            if not base_url.endswith("/data"):
                print("  Not on detail data page yet. Constructing target URL directly...")
                if base_url.endswith("/"):
                    data_url = base_url + "data"
                else:
                    data_url = base_url + "/data"
                print(f"  Direct navigation to: {data_url}")
                page.goto(data_url)
                page.wait_for_timeout(3000)
                
            # Ensure 50 items per page parameters
            current_url = page.url
            if "perPage=50" not in current_url:
                print("  Forcing 50 items per page by updating URL query parameters...")
                if "?" in current_url:
                    if "perPage=" in current_url:
                        target_url = re.sub(r"perPage=\d+", "perPage=50", current_url)
                    else:
                        target_url = current_url + "&perPage=50"
                else:
                    target_url = current_url + "?perPage=50"
                page.goto(target_url)
                page.wait_for_timeout(3000)
                
            print("Waiting for detail data table to load...")
            try:
                page.wait_for_selector("table", timeout=45000)
                print("Table loaded successfully. Starting detail scraper...")
            except Exception:
                print("Error: Table not found on data page. Aborting.")
                browser.close()
                return

            # Prepare detail CSV headers & file
            detail_headers = [
                "Searched Email", "Kode Identitas", "Nama Keluarga/Bangunan/Usaha", "Alamat Prelist",
                "Nomor Urut Bangunan / IDSBR", "NIB", "Email", "Skala Usaha / Jenis Prelist",
                "Jumlah Usaha", "Kode Pos", "Perubahan SLS", "IDSBR UMKM SLS Sama",
                "Status", "Mode", "Petugas Saat Ini", "Keterangan"
            ]
            
            if resume_index > 0 and os.path.exists(output_csv):
                print(f"Appending new detail results to existing '{output_csv}'...")
                csv_file = open(output_csv, "a", newline="", encoding="utf-8")
                csv_writer = csv.writer(csv_file)
            else:
                print(f"Overwriting/initializing '{output_csv}' with headers...")
                csv_file = open(output_csv, "w", newline="", encoding="utf-8")
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(detail_headers)
                csv_file.flush()

            # 7. Scrape Detail Data Mitra
            print(f"Loaded {len(emails)} emails to scrape.")
            for index in range(resume_index, len(emails)):
                email = emails[index]
                print(f"[{index + 1}/{len(emails)}] Searching detail for: {email}")
                
                attempts = 2
                total_scraped = 0
                success = False
                
                for attempt in range(1, attempts + 1):
                    if attempt > 1:
                        print(f"  [Retry] Retry attempt #{attempt} for {email}...")
                    try:
                        search_input = page.locator('input[placeholder="Cari..."]')
                        if search_input.count() == 0:
                            print("  Search input not found! Reloading data page...")
                            page.goto(page.url)
                            page.wait_for_selector("table", timeout=45000)
                            search_input = page.locator('input[placeholder="Cari..."]')
                            
                        search_input.click()
                        search_input.fill("")
                        search_input.fill(email)
                        search_input.press("Enter")
                        
                        wait_for_table_load(page, searched_text=email)
                        
                        page_num = 1
                        current_scraped = 0
                        while True:
                            print(f"  Scraping detail page {page_num}...")
                            scraped_in_page = scrape_page(page, email, csv_writer)
                            current_scraped += scraped_in_page
                            csv_file.flush()
                            
                            next_button = page.locator('button[aria-label="Go to next page"]')
                            if next_button.count() > 0 and next_button.is_visible() and not next_button.is_disabled():
                                print(f"  Navigating to next page...")
                                prev_row_text = page.locator("table tbody tr").first.text_content() if page.locator("table tbody tr").count() > 0 else None
                                next_button.click()
                                page_num += 1
                                wait_for_table_load(page, previous_first_row_text=prev_row_text)
                            else:
                                break
                                
                        total_scraped = current_scraped
                        if total_scraped > 0:
                            print(f"  Finished search for {email}. Total: {total_scraped} rows.")
                            success = True
                            break
                        else:
                            print(f"  Warning: Scraped 0 rows for {email}.")
                            first_row = page.locator("table tbody tr").first
                            first_row_text = first_row.text_content().lower() if first_row.count() > 0 else ""
                            is_genuine_no_data = "tidak ada data" in first_row_text or "empty" in first_row_text or "no data" in first_row_text
                            if is_genuine_no_data:
                                print(f"  Confirmed: No data for {email}.")
                            
                            if attempt < attempts:
                                print(f"  Retrying to ensure fresh state...")
                                try:
                                    page.goto(page.url)
                                    page.wait_for_selector("table", timeout=45000)
                                except Exception:
                                    pass
                            else:
                                print(f"  Finished after {attempts} attempts. Scraped: {total_scraped} rows.")
                                success = True
                    except Exception as e:
                        print(f"  Error processing email {email} (Attempt {attempt}/{attempts}): {e}")
                        if attempt < attempts:
                            try:
                                page.goto(page.url)
                                page.wait_for_selector("table", timeout=45000)
                            except Exception:
                                pass
                        else:
                            print(f"  Failed to process {email} after {attempts} attempts.")
                
                # Save checkpoint
                try:
                    with open(checkpoint_file, "w") as f:
                        json.dump({"last_index": index, "last_email": email, "reverse_order": reverse_order}, f)
                except Exception as e:
                    print(f"Warning saving checkpoint: {e}")

        # Cleanup detail csv and browser
        if run_mode in ["full", "data"]:
            if 'csv_file' in locals() and not csv_file.closed:
                csv_file.close()
            # Remove checkpoint on successful completion
            if os.path.exists(checkpoint_file):
                try:
                    os.remove(checkpoint_file)
                    print("All detail scraping completed. Checkpoint removed.")
                except Exception as e:
                    print(f"Warning removing checkpoint: {e}")
                    
        browser.close()
        
        # 8. Run final data processing and git push
        if run_mode in ["full", "data"]:
            print("\nRunning final data processing pipeline...")
            try:
                import process_data
                process_data.process_data()
            except Exception as proc_err:
                print(f"Warning: Error during final data processing: {proc_err}")

        print("\n" + "="*50)
        print("UNIFIED SCRAPING AND PROCESSING PIPELINE COMPLETED")
        print("="*50)
        
        # Open local dashboard if generated
        if run_mode in ["full", "dashboard"]:
            try:
                html_path = os.path.abspath("index.html")
                if os.path.exists(html_path):
                    print(f"\nMembuka dashboard lokal di browser: file:///{html_path}")
                    webbrowser.open(f"file:///{html_path}")
            except Exception as e:
                print(f"Peringatan: Gagal membuka dashboard di browser: {e}")

if __name__ == "__main__":
    run_unified_scraper()
