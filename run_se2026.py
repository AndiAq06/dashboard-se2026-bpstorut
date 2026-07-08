import os
import re
import csv
import sys
import time
import json
import random
import socket
import subprocess
import atexit
import webbrowser
from playwright.sync_api import sync_playwright
import process_data

chrome_proc = None

@atexit.register
def cleanup_chrome():
    global chrome_proc
    if chrome_proc:
        try:
            if sys.platform == "win32":
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(chrome_proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                chrome_proc.terminate()
                chrome_proc.wait(timeout=3)
        except Exception:
            try:
                chrome_proc.kill()
            except Exception:
                pass

def get_free_port():
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def find_chrome_path():
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def launch_native_chrome(p, user_data_dir="chrome_profile"):
    global chrome_proc
    
    # Clean up orphaned processes using this profile to prevent locks on Windows
    if sys.platform == "win32":
        try:
            profile_pattern = os.path.basename(user_data_dir)
            subprocess.call(['powershell', '-Command', f'Get-CimInstance Win32_Process -Filter "CommandLine like \'%{profile_pattern}%\'" | Remove-CimInstance'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
            
    chrome_path = find_chrome_path()
    if not chrome_path:
        print("ERROR: Google Chrome was not found.", file=sys.stderr)
        sys.exit(1)
        
    abs_user_data_dir = os.path.abspath(user_data_dir)
    os.makedirs(abs_user_data_dir, exist_ok=True)
    
    port = get_free_port()
    print(f"Launching native Chrome on port {port} using profile in '{user_data_dir}'...")
    
    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={abs_user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check"
    ]
    
    proc = subprocess.Popen(cmd)
    chrome_proc = proc
    
    # Wait for Chrome to start
    retries = 10
    connected = False
    while retries > 0:
        time.sleep(0.5)
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                connected = True
                break
        except Exception:
            retries -= 1
            
    if not connected:
        print("ERROR: Failed to connect to the launched Chrome instance.", file=sys.stderr)
        try:
            proc.kill()
        except Exception:
            pass
        sys.exit(1)
        
    print("Connecting Playwright to the Chrome instance...")
    browser = p.chromium.connect_over_cdp(f"http://localhost:{port}")
    return browser, proc

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

    # Clear Chrome profile if starting fresh
    if "--fresh" in sys.argv:
        print("Fresh run requested. Clearing existing Chrome profile...")
        profile_dir = os.path.abspath("chrome_profile")
        if os.path.exists(profile_dir):
            try:
                import shutil
                shutil.rmtree(profile_dir)
                print("Chrome profile cleared.")
            except Exception as e:
                print(f"Warning: could not clear Chrome profile: {e}")

    with sync_playwright() as p:
        browser, chrome_proc = launch_native_chrome(p, "chrome_profile")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        
        # 2. Navigate to App (automatically redirects to login if needed)
        print("Navigating to BPS FASIH homepage...")
        page.goto("https://fasih-sm.bps.go.id/", timeout=120000)
        
        # Wait for the page state to stabilize
        login_btn = page.locator("text=Login SSO BPS")
        username_input = page.locator("#username")
        search_input = page.locator('input[placeholder="Cari survei..."]')
        
        state = None
        for i in range(60): # Up to 30 seconds
            if search_input.count() > 0 and search_input.is_visible():
                state = "logged_in"
                break
            elif username_input.count() > 0 and username_input.is_visible():
                state = "login_form"
                break
            elif login_btn.count() > 0 and login_btn.is_visible():
                state = "landing_page"
                break
            page.wait_for_timeout(500)
            
        print(f"Detected state: {state}")
        
        if state == "landing_page":
            print("Clicking 'Login SSO BPS'...")
            login_btn.first.click()
            page.wait_for_timeout(3000)
            
            # Now wait for the login form
            for _ in range(30):
                if username_input.count() > 0 and username_input.is_visible():
                    state = "login_form"
                    break
                page.wait_for_timeout(500)
                
        if state == "login_form":
            print(f"Filling credentials for user: {username}...")
            username_input.fill(username)
            page.locator("#password").fill(password)
            page.locator("#kc-login").click()
            page.wait_for_timeout(5000)
                
        # Wait for redirect to app workspace (either old /app or new /survey-collection/survey)
        print("Waiting for redirect to app workspace...")
        try:
            page.locator('input[placeholder="Cari survei..."]').wait_for(state="visible", timeout=45000)
            print("Successfully reached the app workspace!")
        except Exception:
            print("Warning: Redirection to app workspace timeout. Checking current URL: " + page.url)
            # If we are not on the app workspace, try to navigate there directly
            if "survey-collection" not in page.url and "app" not in page.url:
                print("Navigating to survey-collection/survey explicitly...")
                page.goto("https://fasih-sm.bps.go.id/survey-collection/survey", timeout=90000)
                page.wait_for_timeout(5000)
                
        # Final check to ensure we are in the app workspace
        page.locator('input[placeholder="Cari survei..."]').wait_for(state="visible", timeout=30000)
            
        # Save session immediately
        context.storage_state(path=auth_file)
        print(f"Session state saved to '{auth_file}'")
        
        # 3. Search and select survey
        print("Searching for 'SENSUS EKONOMI 2026'...")
        if "survey-collection" not in page.url and not page.url.endswith("/app") and "/app/surveys" not in page.url:
            page.goto("https://fasih-sm.bps.go.id/survey-collection/survey")
            page.wait_for_timeout(2000)
            
        search_input = page.locator('input[placeholder="Cari survei..."]')
        search_input.wait_for(state="visible", timeout=30000)
        search_input.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.wait_for_timeout(random.randint(150, 300))
        search_input.press_sequentially("SENSUS EKONOMI 2026", delay=random.randint(50, 120))
        page.wait_for_timeout(random.randint(200, 400))
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
                "SUBMITTED RESPONDENT": "SUBMITTED BY Pencacah",
                "REJECTED BY PENGAWAS": "REJECTED BY Pengawas",
                "REJECTED BY ADMIN KABUPATEN": "REJECTED BY Pengawas",
                "REVOKED BY PENGAWAS": "REJECTED BY Pengawas",
                "EDITED BY PENGAWAS": "REJECTED BY Pengawas",
                "APPROVED BY PENGAWAS": "APPROVED BY Pengawas",
            }
            
            # Get survey ID and period ID from active URL
            current_url = page.url
            match = re.search(r"/surveys?/([^/]+)/([^/]+)", current_url)
            if not match:
                print(f"Error: Could not parse survey ID and period ID from URL: {current_url}")
                survey_id = "a0429e96-51a5-477b-a415-485f9c153004"
                period_id = "fd68e454-ba45-4b85-8205-f3bf777ded24"
            else:
                survey_id = match.group(1)
                period_id = match.group(2)
            print(f"Active Survey ID: {survey_id}, Period ID: {period_id}")

            # Get role IDs
            role_ids = {
                "Pengawas": "93bcf446-c4c1-4462-8ed0-4b0f7ae89e52", # Fallback PML
                "Pencacah": "6d7d919a-45e5-4779-bb87-2905b49fd31a", # Fallback PPL
            }
            
            try:
                js_roles_script = """
                    async (surveyId) => {
                        const xsrfToken = document.cookie.split('; ').find(row => row.startsWith('XSRF-TOKEN='))?.split('=')[1] || '';
                        const response = await fetch(`/app/api/survey/api/v1/survey-roles?surveyId=${surveyId}`, {
                            headers: {
                                'X-XSRF-TOKEN': xsrfToken
                            }
                        });
                        if (!response.ok) return [];
                        return await response.json();
                    }
                """
                roles_data = page.evaluate(js_roles_script, survey_id)
                if roles_data and isinstance(roles_data, list):
                    for r in roles_data:
                        name_lower = r.get("name", "").lower()
                        alias_lower = r.get("alias", "").lower()
                        role_id = r.get("id")
                        if not role_id:
                            continue
                        if "pengawas" in name_lower or "pml" in alias_lower:
                            role_ids["Pengawas"] = role_id
                        elif "pencacah" in name_lower or "ppl" in alias_lower:
                            role_ids["Pencacah"] = role_id
                    print(f"Dynamically resolved survey roles: {role_ids}")
            except Exception as e:
                print(f"Warning: Failed to fetch roles dynamically: {e}. Using fallback role IDs.")

            # JavaScript to fetch all pages for a role using API
            js_rekap_script = """
                async (params) => {
                    const { surveyPeriodId, surveyRoleId } = params;
                    const xsrfToken = document.cookie.split('; ').find(row => row.startsWith('XSRF-TOKEN='))?.split('=')[1] || '';
                    
                    let allItems = [];
                    let pageNum = 0;
                    const size = 10;
                    
                    while (true) {
                        const payload = {
                            "surveyPeriodId": surveyPeriodId,
                            "surveyRoleId": surveyRoleId,
                            "size": size,
                            "page": pageNum,
                            "search": "",
                            "target": "TARGET_ONLY",
                            "region": {
                                "region1Id": null, "region2Id": null, "region3Id": null, "region4Id": null, "region5Id": null,
                                "region6Id": null, "region7Id": null, "region8Id": null, "region9Id": null, "region10Id": null
                            },
                            "regionSummaryLevel": 6
                        };
                        
                        const response = await fetch('/app/api/analytic/api/v2/assignment/report-progress-by-responsibility', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-XSRF-TOKEN': xsrfToken
                            },
                            body: JSON.stringify(payload)
                        });
                        
                        if (!response.ok) {
                            throw new Error('HTTP error ' + response.status);
                        }
                        
                        const result = await response.json();
                        const content = result.data?.content || [];
                        allItems.push(...content);
                        
                        const isLast = result.data?.last ?? true;
                        if (isLast || content.length === 0) {
                            break;
                        }
                        
                        pageNum += 1;
                    }
                    
                    return allItems;
                }
            """
            
            for category in ["Pengawas", "Pencacah"]:
                role_id = role_ids[category]
                print(f"\nFetching Rekap for Category {category} (Role ID: {role_id}) via API...")
                
                try:
                    items = page.evaluate(js_rekap_script, {"surveyPeriodId": period_id, "surveyRoleId": role_id})
                    print(f"  Successfully fetched {len(items)} records via API.")
                    
                    for item in items:
                        email = item.get("email") or item.get("username")
                        if not email:
                            continue
                        email = email.strip()
                        
                        # Loop through regions / SLS codes
                        regions = item.get("regionSummary") or []
                        for reg in regions:
                            sls_code = reg.get("regionCode")
                            if not sls_code:
                                continue
                            sls_code = sls_code.strip()
                            
                            key = (category, email, sls_code)
                            if key not in scraped_data_dict:
                                scraped_data_dict[key] = {col: 0 for col in status_columns}
                                
                            # Fill counts
                            breakdowns = reg.get("statusBreakdown") or []
                            for bd in breakdowns:
                                raw_status = bd.get("status") or ""
                                count = bd.get("count") or 0
                                
                                # Match status case-insensitively
                                matched_col = status_mapping.get(raw_status.upper())
                                if matched_col:
                                    scraped_data_dict[key][matched_col] = int(count)
                except Exception as eval_err:
                    print(f"  Error fetching rekap for {category}: {eval_err}")
     
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

            # Get period_id from active URL
            current_url = page.url
            match = re.search(r"/app/surveys/([^/]+)/([^/]+)/data", current_url)
            if not match:
                print("Error: Could not parse survey ID and period ID from URL. URL: " + current_url)
                browser.close()
                return
            survey_id = match.group(1)
            period_id = match.group(2)
            print(f"Parsed Survey ID: {survey_id}, Period ID: {period_id}")

            js_fetch_script = """
                async (params) => {
                    const { email, periodId } = params;
                    const xsrfToken = document.cookie.split('; ').find(row => row.startsWith('XSRF-TOKEN='))?.split('=')[1] || '';
                    
                    let allRecords = [];
                    let start = 0;
                    const length = 100;
                    
                    while (true) {
                        const payload = {
                            "start": start,
                            "length": length,
                            "columns": [
                                {"data": "id", "orderable": true},
                                {"data": "codeIdentity", "orderable": true},
                                {"data": "data1", "orderable": true},
                                {"data": "data2", "orderable": true},
                                {"data": "data3", "orderable": true},
                                {"data": "data4", "orderable": true},
                                {"data": "data5", "orderable": true},
                                {"data": "data6", "orderable": true},
                                {"data": "data7", "orderable": true},
                                {"data": "data8", "orderable": true},
                                {"data": "data9", "orderable": true},
                                {"data": "data10", "orderable": true}
                            ],
                            "order": [],
                            "search": {
                                "value": email,
                                "regex": false
                            },
                            "assignmentExtraParam": {
                                "surveyPeriodId": periodId,
                                "assignmentErrorStatusType": -1,
                                "filterTargetType": "TARGET_ONLY"
                            }
                        };
                        
                        const response = await fetch('/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-XSRF-TOKEN': xsrfToken
                            },
                            body: JSON.stringify(payload)
                        });
                        
                        if (!response.ok) {
                            throw new Error('HTTP error ' + response.status);
                        }
                        
                        const result = await response.json();
                        const dataList = result.searchData || [];
                        allRecords.push(...dataList);
                        
                        const totalHit = result.totalHit || 0;
                        if (allRecords.length >= totalHit || dataList.length === 0) {
                            break;
                        }
                        
                        start += length;
                    }
                    
                    return allRecords;
                }
            """

            # 7. Scrape Detail Data Mitra
            print(f"Loaded {len(emails)} emails to scrape.")
            failed_emails = []
            for index in range(resume_index, len(emails)):
                email = emails[index]
                print(f"[{index + 1}/{len(emails)}] Fetching detail via API for: {email}")
                
                # Small safety delay between requests
                if index > resume_index:
                    delay_seconds = random.uniform(0.5, 1.2)
                    time.sleep(delay_seconds)
                
                attempts = 3
                success = False
                
                for attempt in range(1, attempts + 1):
                    if attempt > 1:
                        print(f"  [Retry] Retry attempt #{attempt} for {email}...")
                    try:
                        records = page.evaluate(js_fetch_script, {"email": email, "periodId": period_id})
                        
                        total_scraped = 0
                        for item in records:
                            code_identity = item.get("codeIdentity") or "-"
                            data1 = item.get("data1") or "-"
                            data2 = item.get("data2") or "-"
                            data3 = item.get("data3") or "-"
                            data4 = item.get("data4") or "-"
                            data5 = item.get("data5") or "-"
                            data6 = item.get("data6") or "-"
                            data7 = item.get("data7") or "-"
                            data8 = item.get("data8") or "-"
                            data9 = item.get("data9") or "-"
                            data10 = item.get("data10") or "-"
                            status = (item.get("assignmentStatusAlias") or "open").lower()
                            
                            modes = item.get("mode") or []
                            mode = ", ".join(modes) if modes else "-"
                            
                            username = item.get("currentUserUsername") or ""
                            role_name = item.get("currentUserSurveyRoleName") or ""
                            petugas = f"{username}{role_name}" if username or role_name else "-"
                            
                            keterangan = "-"
                            
                            csv_writer.writerow([
                                email, code_identity, data1, data2, data3, data4, data5, data6, data7, data8, data9, data10, status, mode, petugas, keterangan
                            ])
                            total_scraped += 1
                            
                        csv_file.flush()
                        print(f"  Finished search for {email}. Total: {total_scraped} rows.")
                        success = True
                        break
                    except Exception as e:
                        print(f"  Error processing email {email} (Attempt {attempt}/{attempts}): {e}")
                        if attempt < attempts:
                            try:
                                page.goto(current_url)
                                page.wait_for_selector("table", timeout=45000)
                            except Exception:
                                pass
                            time.sleep(attempt * 2)
                        else:
                            print(f"  Failed to process {email} after {attempts} attempts. Will retry at the end.")
                            failed_emails.append(email)
                
                # Save checkpoint
                try:
                    with open(checkpoint_file, "w") as f:
                        json.dump({"last_index": index, "last_email": email, "reverse_order": reverse_order}, f)
                except Exception as e:
                    print(f"Warning saving checkpoint: {e}")

            # 7b. Retry failed emails at the end until all are successfully retrieved
            if failed_emails:
                print(f"\n--- Phase 3b: Retrying {len(failed_emails)} failed emails at the end ---")
                retry_round = 1
                while failed_emails:
                    print(f"\nRetry Round #{retry_round} for {len(failed_emails)} remaining emails...")
                    still_failed = []
                    for idx, email in enumerate(failed_emails):
                        print(f"[{idx + 1}/{len(failed_emails)}] Retrying: {email}")
                        
                        # Small delay between retry requests
                        delay_seconds = random.uniform(1.0, 2.0)
                        time.sleep(delay_seconds)
                        
                        success = False
                        attempts = 3
                        for attempt in range(1, attempts + 1):
                            if attempt > 1:
                                print(f"  [Retry] Retry attempt #{attempt} for {email}...")
                            try:
                                records = page.evaluate(js_fetch_script, {"email": email, "periodId": period_id})
                                
                                total_scraped = 0
                                for item in records:
                                    code_identity = item.get("codeIdentity") or "-"
                                    data1 = item.get("data1") or "-"
                                    data2 = item.get("data2") or "-"
                                    data3 = item.get("data3") or "-"
                                    data4 = item.get("data4") or "-"
                                    data5 = item.get("data5") or "-"
                                    data6 = item.get("data6") or "-"
                                    data7 = item.get("data7") or "-"
                                    data8 = item.get("data8") or "-"
                                    data9 = item.get("data9") or "-"
                                    data10 = item.get("data10") or "-"
                                    status = (item.get("assignmentStatusAlias") or "open").lower()
                                    
                                    modes = item.get("mode") or []
                                    mode = ", ".join(modes) if modes else "-"
                                    
                                    username = item.get("currentUserUsername") or ""
                                    role_name = item.get("currentUserSurveyRoleName") or ""
                                    petugas = f"{username}{role_name}" if username or role_name else "-"
                                    
                                    keterangan = "-"
                                    
                                    csv_writer.writerow([
                                        email, code_identity, data1, data2, data3, data4, data5, data6, data7, data8, data9, data10, status, mode, petugas, keterangan
                                    ])
                                    total_scraped += 1
                                    
                                csv_file.flush()
                                print(f"  Finished search for {email}. Total: {total_scraped} rows.")
                                success = True
                                break
                            except Exception as e:
                                print(f"  Error retrying email {email} (Attempt {attempt}/{attempts}): {e}")
                                # Reload page
                                try:
                                    page.goto(current_url)
                                    page.wait_for_selector("table", timeout=45000)
                                except Exception:
                                    pass
                                time.sleep(attempt * 2)
                        
                        if not success:
                            still_failed.append(email)
                    
                    failed_emails = still_failed
                    retry_round += 1
                    if failed_emails:
                        print(f"Round finished. {len(failed_emails)} emails still failed. Waiting 5 seconds before next round...")
                        time.sleep(5)
                print("All failed emails processed successfully!")

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
        cleanup_chrome()
        
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
