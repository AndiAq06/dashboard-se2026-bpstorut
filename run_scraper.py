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

def load_emails(file_path):
    if not os.path.exists(file_path):
        print(f"Error: Email list file '{file_path}' not found.")
        sys.exit(1)
    with open(file_path, "r", encoding="utf-8") as f:
        emails = [line.strip() for line in f if line.strip()]
    return emails

def wait_for_table_load(page, searched_text=None, previous_first_row_text=None, timeout=45000):
    start_time = time.time()
    
    # 1. Wait a brief moment for actions to register and loading states to trigger
    page.wait_for_timeout(500)
    
    # 2. Wait for loader spinners to disappear (if they appear)
    try:
        loaders = page.locator("svg.tabler-icon-loader, svg.tabler-icon-loader-2")
        if loaders.count() > 0:
            loaders.first.wait_for(state="hidden", timeout=timeout)
    except Exception:
        pass

    # 3. Dynamic verification loop
    while time.time() - start_time < (timeout / 1000.0):
        rows = page.locator("table tbody tr")
        row_count = rows.count()
        
        if row_count > 0:
            first_row_text = rows.first.text_content()
            first_row_text_lower = first_row_text.lower()
            
            # Check for "No data" placeholder
            is_no_data = "tidak ada data" in first_row_text_lower or "empty" in first_row_text_lower or "no data" in first_row_text_lower
            
            # Condition A: Waiting for new page content (first row text should differ from old page)
            if previous_first_row_text is not None:
                if first_row_text != previous_first_row_text:
                    break
            
            # Condition B: Waiting for search results matching a term
            elif searched_text is not None:
                if is_no_data:
                    break
                
                # Check if the search term exists within the table body text
                tbody_text = page.locator("table tbody").text_content().lower()
                if searched_text.lower() in tbody_text:
                    break
            
            # Default: If no conditions specified, just wait for any row to be present
            else:
                break
        
        # Sleep and retry if table hasn't updated/loaded yet
        time.sleep(0.5)
        
    # 4. Extra safety buffer for UI/React state settling
    time.sleep(1.0)

def scrape_page(page, searched_email, csv_writer):
    # Find all data rows in the table body
    rows_locator = page.locator("table tbody tr")
    row_count = rows_locator.count()
    
    if row_count == 0:
        print(f"  No rows found in table.")
        return 0
        
    # Check if first row is a placeholder message (like 'Tidak ada data')
    first_row_text = rows_locator.first.text_content().lower()
    if "tidak ada data" in first_row_text or "empty" in first_row_text or "no data" in first_row_text:
        print(f"  No data matching search.")
        return 0
        
    scraped_count = 0
    for i in range(row_count):
        cols = rows_locator.nth(i).locator("td").all_text_contents()
        
        # Based on our analysis, the table has 17 columns:
        # Col 0: Checkbox
        # Col 1: Kode Identitas
        # Col 2: Nama Keluarga/Bangunan/Usaha
        # Col 3: Alamat Prelist
        # Col 4: Nomor Urut Bangunan / IDSBR
        # Col 5: NIB
        # Col 6: Email
        # Col 7: Skala Usaha / Jenis Prelist
        # Col 8: Jumlah Usaha
        # Col 9: Kode Pos
        # Col 10: Perubahan SLS
        # Col 11: IDSBR UMKM SLS Sama
        # Col 12: Status
        # Col 13: Mode
        # Col 14: Petugas Saat Ini
        # Col 15: Keterangan
        # Col 16: Action Button
        
        if len(cols) >= 16:
            # Clean text values (strip whitespace)
            cleaned_cols = [c.strip() for c in cols]
            
            # Write row to CSV: searched email + table columns (excluding checkbox at index 0 and action at index 16)
            csv_writer.writerow([searched_email] + cleaned_cols[1:16])
            scraped_count += 1
            
    print(f"  Scraped {scraped_count} rows from current page.")
    return scraped_count

def run_scraper(use_test_emails=False):
    email_file = os.path.join("data", "email_mitra_test.txt" if use_test_emails else "email_mitra.txt")
    auth_file = "auth_state.json"
    output_csv = "scraped_data.csv"
    checkpoint_file = "checkpoint.json"
    
    emails = load_emails(email_file)
    
    # Check for order argument in command line or prompt user
    reverse_order = False
    if "--bottom" in sys.argv or "--reverse" in sys.argv:
        reverse_order = True
        print("Scraping order set via CLI: BOTTOM TO TOP (Reversed).")
    elif "--top" in sys.argv:
        reverse_order = False
        print("Scraping order set via CLI: TOP TO BOTTOM (Normal).")
    else:
        # Interactive prompt if no CLI argument for order is specified
        print("\nPilih urutan scraping email:")
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
            
    # Reverse emails if reverse_order is True
    if reverse_order:
        emails.reverse()
        
    print(f"Loaded {len(emails)} emails from '{email_file}' to scrape.")
    print("Scraping queue preview:")
    if len(emails) <= 6:
        for i, email in enumerate(emails):
            print(f"  {i+1}. {email}")
    else:
        for i in range(3):
            print(f"  {i+1}. {emails[i]}")
        print("  ...")
        for i in range(len(emails) - 3, len(emails)):
            print(f"  {i+1}. {emails[i]}")
            
    # Check if we should start fresh
    use_fresh = "--fresh" in sys.argv
    resume_index = 0
    
    if not use_fresh and os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, "r") as f:
                cp = json.load(f)
                last_email = cp.get("last_email")
                cp_reverse = cp.get("reverse_order", None)
                
                # Check if the checkpoint's order is different from the current run's order
                if cp_reverse is not None and cp_reverse != reverse_order:
                    print(f"\n[!] PERINGATAN: Urutan checkpoint ({'Bawah ke Atas' if cp_reverse else 'Atas ke Bawah'}) "
                          f"berbeda dengan urutan jalankan saat ini ({'Bawah ke Atas' if reverse_order else 'Atas ke Bawah'}).")
                    print("Melanjutkan dengan arah berbeda dapat menyebabkan email terlewat atau terduplikat.")
                    try:
                        choice = input("Mulai baru dari awal (fresh)? (y/n) [y]: ").strip().lower()
                        if choice == "n":
                            print("Melanjutkan dari email terakhir...")
                        else:
                            use_fresh = True
                    except Exception:
                        use_fresh = True
                
                if not use_fresh:
                    # Try to locate by email string instead of index
                    if last_email and last_email in emails:
                        resume_index = emails.index(last_email) + 1
                        if resume_index < len(emails):
                            print(f"Resuming from checkpoint: found last email '{last_email}' in the list. "
                                  f"Starting at email #{resume_index + 1} ({emails[resume_index]})")
                        else:
                            resume_index = 0
                            print(f"Checkpoint email '{last_email}' is the last item in the list. Starting fresh.")
                    else:
                        # Fallback to index if email is not found
                        resume_index = cp.get("last_index", 0)
                        if resume_index < len(emails):
                            print(f"Resuming from checkpoint: starting at email #{resume_index + 1} ({emails[resume_index]})")
                        else:
                            resume_index = 0
                            print("Checkpoint index exceeds email list length or email not found. Starting fresh.")
        except Exception as cp_err:
            print(f"Warning: Could not read checkpoint file: {cp_err}. Starting fresh.")
            
    # Prepare CSV file
    csv_headers = [
        "Searched Email", "Kode Identitas", "Nama Keluarga/Bangunan/Usaha", "Alamat Prelist",
        "Nomor Urut Bangunan / IDSBR", "NIB", "Email", "Skala Usaha / Jenis Prelist",
        "Jumlah Usaha", "Kode Pos", "Perubahan SLS", "IDSBR UMKM SLS Sama",
        "Status", "Mode", "Petugas Saat Ini", "Keterangan"
    ]
    
    if resume_index > 0 and os.path.exists(output_csv):
        print(f"Appending new results to existing '{output_csv}'...")
        csv_file = open(output_csv, "a", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
    else:
        print(f"Overwriting/initializing '{output_csv}' with headers...")
        csv_file = open(output_csv, "w", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(csv_headers)
        csv_file.flush()
        
    print(f"Output will be saved/appended to '{output_csv}'")
    
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
        
        # Open BPS FASIH
        print("Navigating to BPS FASIH website...")
        page.goto("https://fasih-sm.bps.go.id/")
        
        # Regex pattern for survey data page URL
        # Format: https://fasih-sm.bps.go.id/app/surveys/<survey-id>/<period-id>/data
        target_pattern = re.compile(r"/app/surveys/[^/]+/[^/]+/data")
        
        print("\n" + "="*70)
        print("WAITING FOR TARGET PAGE:")
        print("Please log in (if not already logged in) and click/navigate to the survey data table.")
        print("The script will automatically detect when you reach the page and start scraping.")
        print("="*70 + "\n")
        
        # Wait indefinitely until URL matches the target pattern
        try:
            page.wait_for_url(target_pattern, timeout=0)
        except Exception as e:
            print(f"Error waiting for target page: {e}")
            browser.close()
            return
            
        # We are on the target page!
        current_url = page.url
        print(f"\nTarget survey page detected: {current_url}")
        
        # Save session immediately so user doesn't have to log in next time
        context.storage_state(path=auth_file)
        print(f"Session state saved to '{auth_file}'")
        
        # Ensure we display 50 items per page (force URL parameter)
        if "perPage=50" not in current_url:
            print("Forcing 50 items per page by updating URL query parameters...")
            if "?" in current_url:
                if "perPage=" in current_url:
                    target_url = re.sub(r"perPage=\d+", "perPage=50", current_url)
                else:
                    target_url = current_url + "&perPage=50"
            else:
                target_url = current_url + "?perPage=50"
                
            print(f"Redirecting to: {target_url}")
            page.goto(target_url)
            page.wait_for_url(target_pattern, timeout=10000)
            
        # Wait for table to load
        print("Waiting for table to load...")
        try:
            page.wait_for_selector("table", timeout=45000)
            print("Table loaded successfully. Starting scraper loop...")
        except Exception:
            print("Error: Table not found on target page. Aborting.")
            browser.close()
            csv_file.close()
            return
            
        # Get period_id from active URL
        current_url = page.url
        match = re.search(r"/app/surveys/([^/]+)/([^/]+)/data", current_url)
        if not match:
            print("Error: Could not parse survey ID and period ID from URL. URL: " + current_url)
            browser.close()
            csv_file.close()
            return
        survey_id = match.group(1)
        period_id = match.group(2)
        print(f"Parsed Survey ID: {survey_id}, Period ID: {period_id}")

        js_fetch_bulk_script = """
            async (params) => {
                const { emails, periodId } = params;
                const xsrfToken = document.cookie.split('; ').find(row => row.startsWith('XSRF-TOKEN='))?.split('=')[1] || '';
                
                let allRecords = [];
                const fetchedIds = new Set();
                
                const postAPI = async (start, length, searchValue) => {
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
                            "value": searchValue,
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
                    
                    return await response.json();
                };
                
                // We fetch email-by-email in parallel (concurrency 12)
                // This is 100% safe from server-side query caps!
                console.log("Fetching details email-by-email in parallel...");
                const fetchForEmail = async (email) => {
                    let start = 0;
                    const length = 250;
                    while (true) {
                        const result = await postAPI(start, length, email);
                        const dataList = result.searchData || [];
                        for (const item of dataList) {
                            const itemId = item.id;
                            if (!fetchedIds.has(itemId)) {
                                fetchedIds.add(itemId);
                                allRecords.push(item);
                            }
                        }
                        const total = result.totalHit || 0;
                        const currentFetched = dataList.length;
                        if (currentFetched === 0 || start + currentFetched >= total) {
                            break;
                        }
                        start += length;
                    }
                };
                
                const concurrencyLimit = 12;
                const queue = [...emails];
                const activePromises = [];
                
                while (queue.length > 0 || activePromises.length > 0) {
                    while (activePromises.length < concurrencyLimit && queue.length > 0) {
                        const email = queue.shift();
                        const p = fetchForEmail(email).then(() => {
                            activePromises.splice(activePromises.indexOf(p), 1);
                        }).catch((err) => {
                            console.error("Error fetching for email " + email + ":", err);
                            activePromises.splice(activePromises.indexOf(p), 1);
                        });
                        activePromises.push(p);
                    }
                    if (activePromises.length > 0) {
                        await Promise.race(activePromises);
                    }
                }
                
                // Also fetch by status to get any records not mapped to emails
                console.log("Fetching additional records by status...");
                const statuses = ["approved by pengawas", "submitted by pencacah", "rejected by pengawas"];
                const fetchByStatus = async (statusName) => {
                    let start = 0;
                    const length = 250;
                    while (true) {
                        const result = await postAPI(start, length, statusName);
                        const dataList = result.searchData || [];
                        for (const item of dataList) {
                            const itemId = item.id;
                            if (!fetchedIds.has(itemId)) {
                                fetchedIds.add(itemId);
                                allRecords.push(item);
                            } else {
                                const existing = allRecords.find(r => r.id === itemId);
                                if (existing) {
                                    existing.assignmentStatusAlias = statusName;
                                }
                            }
                        }
                        const total = result.totalHit || 0;
                        const currentFetched = dataList.length;
                        if (currentFetched === 0 || start + currentFetched >= total) {
                            break;
                        }
                        start += length;
                    }
                };
                
                await Promise.all(statuses.map(s => fetchByStatus(s).catch(e => console.error("Error status " + s, e))));
                
                return allRecords;
            }
        """

        # Load SLS code to PPL email mapping for resolving Searched Email column
        print("Loading SLS code to PPL email mappings...")
        sls_to_email = {}
        try:
            ppl_file = "email_ppl.csv"
            if not os.path.exists(ppl_file):
                ppl_file = os.path.join("data", "email_ppl.csv")
            
            ppl_name_to_email = {}
            if os.path.exists(ppl_file):
                with open(ppl_file, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = row.get('Nama PPL', '').strip()
                        email = row.get('email', '').strip().lower()
                        if email:
                            ppl_name_to_email[process_data.normalize_name(name)] = email
            
            pml_ppl_file = os.path.join("data", "pml_ppl.csv")
            if os.path.exists(pml_ppl_file):
                with open(pml_ppl_file, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = row.get('nama_petugas', '').strip()
                        email = row.get('email', '').strip().lower()
                        role = row.get('jabatan_petugas', '').strip().upper()
                        if email and name and role == "PPL":
                            ppl_name_to_email[process_data.normalize_name(name)] = email

            wilkerstat_map = process_data.load_muatan_wilkerstat()
            for sls_16, details in wilkerstat_map.items():
                ppl_name = details['ppl_name']
                ppl_email = ppl_name_to_email.get(process_data.normalize_name(ppl_name), "")
                if ppl_email:
                    sls_to_email[sls_16] = ppl_email
            print(f"Successfully loaded {len(sls_to_email)} SLS-to-email mapping entries.")
        except Exception as mapping_err:
            print(f"Warning: Failed to load SLS to email mapping: {mapping_err}")

        # Fetch detail data in bulk
        print("\nFetching ALL details in bulk via API...")
        try:
            records = page.evaluate(js_fetch_bulk_script, {"emails": emails, "periodId": period_id})
            print(f"Successfully fetched a total of {len(records)} records.")
            
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
                
                # Resolve searched email
                digits_only = "".join([c for c in code_identity if c.isdigit()])
                sls_16 = digits_only[:16]
                
                email_col = ""
                if sls_16 in sls_to_email:
                    email_col = sls_to_email[sls_16]
                else:
                    if "@" in username:
                        email_col = username.strip().lower()
                    else:
                        email_col = "tidak_teridentifikasi@gmail.com"
                        
                csv_writer.writerow([
                    email_col, code_identity, data1, data2, data3, data4, data5, data6, data7, data8, data9, data10, status, mode, petugas, keterangan
                ])
                total_scraped += 1
                
            csv_file.flush()
            print(f"Finished bulk writing. Total records processed: {total_scraped}")
        except Exception as e:
            print(f"ERROR: Failed to run bulk API scraper: {e}")
            sys.exit(1)
                    

                
        # Cleanup
        csv_file.close()
        browser.close()
        cleanup_chrome()
        
        # Remove checkpoint on successful completion of all emails
        if os.path.exists(checkpoint_file):
            try:
                os.remove(checkpoint_file)
                print("Scraping completed successfully. Checkpoint file removed.")
            except Exception as rm_err:
                print(f"Warning: Could not remove checkpoint file: {rm_err}")
                
        print(f"\nAll scraping completed successfully! Data saved in '{output_csv}'")
        
        # Run the data processing pipeline (which maps subdistricts, copies to dashboard, writes timestamp, and pushes to Git)
        try:
            import process_data
            process_data.process_data()
        except Exception as proc_err:
            print(f"Warning: Error during post-scrape data processing: {proc_err}")

if __name__ == "__main__":
    # Check if user passed --test flag to use email_mitra_test.txt
    use_test = "--test" in sys.argv
    run_scraper(use_test_emails=use_test)
