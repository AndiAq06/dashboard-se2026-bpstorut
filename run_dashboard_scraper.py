import os
import csv
import sys
import time
import re
import random
import socket
import subprocess
import atexit
from playwright.sync_api import sync_playwright

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
        cleanup_chrome()

if __name__ == "__main__":
    main()
