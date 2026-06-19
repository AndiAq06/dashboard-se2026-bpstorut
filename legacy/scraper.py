import os
import csv
import sys
import time
from playwright.sync_api import sync_playwright

def load_emails(file_path):
    if not os.path.exists(file_path):
        print(f"Error: Email list file '{file_path}' not found.")
        sys.exit(1)
    with open(file_path, "r", encoding="utf-8") as f:
        emails = [line.strip() for line in f if line.strip()]
    return emails

def wait_for_table_load(page, timeout=45000):
    # Wait for network requests to finish
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass
    
    # Wait for any loader icons (like tabler-icon-loader) to disappear if they exist
    try:
        loaders = page.locator("svg.tabler-icon-loader, svg.tabler-icon-loader-2")
        if loaders.count() > 0:
            loaders.first.wait_for(state="hidden", timeout=timeout)
    except Exception:
        pass
        
    # Extra safety buffer for rendering
    time.sleep(1.5)

def scrape_page(page, searched_email, csv_writer):
    # Find all data rows in the table body
    rows_locator = page.locator("table tbody tr")
    row_count = rows_locator.count()
    
    # Check if there are no data rows or if the row contains "tidak ada data" / "no data"
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

def main():
    email_file = "email_mitra.txt"
    auth_file = "auth_state.json"
    url_file = "target_url.txt"
    output_csv = "scraped_data.csv"
    
    # Check prerequisites
    if not os.path.exists(auth_file):
        print(f"Error: Auth state file '{auth_file}' not found. Please run login.py first.")
        sys.exit(1)
        
    if not os.path.exists(url_file):
        print(f"Error: Target URL file '{url_file}' not found. Please run login.py first.")
        sys.exit(1)
        
    import re
    with open(url_file, "r", encoding="utf-8") as f:
        target_url = f.read().strip()
    
    # Force perPage=50 to maximize items per page
    if "perPage=" in target_url:
        target_url = re.sub(r"perPage=\d+", "perPage=50", target_url)
    else:
        target_url = target_url + ("&" if "?" in target_url else "?") + "perPage=50"
        
    emails = load_emails(email_file)
    print(f"Loaded {len(emails)} emails to scrape.")
    
    # Prepare CSV file
    csv_headers = [
        "Searched Email", "Kode Identitas", "Nama Keluarga/Bangunan/Usaha", "Alamat Prelist",
        "Nomor Urut Bangunan / IDSBR", "NIB", "Email", "Skala Usaha / Jenis Prelist",
        "Jumlah Usaha", "Kode Pos", "Perubahan SLS", "IDSBR UMKM SLS Sama",
        "Status", "Mode", "Petugas Saat Ini", "Keterangan"
    ]
    
    # Check if CSV already exists to decide whether to write header
    file_exists = os.path.exists(output_csv)
    
    # Open CSV for appending
    csv_file = open(output_csv, "a", newline="", encoding="utf-8")
    csv_writer = csv.writer(csv_file)
    
    if not file_exists:
        csv_writer.writerow(csv_headers)
        csv_file.flush()
        
    print(f"Output will be appended to '{output_csv}'")
    
    with sync_playwright() as p:
        # Launch browser (headed so you can monitor it, but can be changed to headless=True)
        print("Launching browser...")
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        
        # Create context using saved storage state
        context = browser.new_context(storage_state=auth_file)
        page = context.new_page()
        
        # Navigate to target survey URL
        print(f"Navigating to survey URL: {target_url}")
        page.goto(target_url)
        
        # Wait for table to appear (up to 10 seconds)
        try:
            print("Waiting for table to load...")
            page.wait_for_selector("table", timeout=45000)
            print("Table loaded successfully.")
        except Exception as e:
            print(f"Warning: Table not found! Current URL: {page.url}")
            page.screenshot(path="table_not_found_debug.png")
            print("Debug screenshot saved to 'table_not_found_debug.png'")
            input("Press Enter to continue anyway or Ctrl+C to abort...")
            
        # Select items-per-page to 50 if it's not already
        try:
            per_page_btn = page.locator('button:has-text("50")')
            if per_page_btn.count() == 0:
                # If the button currently shows something else, e.g. "10" or "25", let's select 50
                # But typically the saved page shows "50" already.
                pass
        except Exception as e:
            print(f"Could not verify items per page selection: {e}")
            
        # Loop through emails
        for index, email in enumerate(emails, 1):
            print(f"[{index}/{len(emails)}] Searching for: {email}")
            
            attempts = 2
            total_scraped = 0
            success = False
            
            for attempt in range(1, attempts + 1):
                if attempt > 1:
                    print(f"  [Retry] Melakukan percobaan ulang ke-{attempt} untuk {email}...")
                try:
                    # Locate search input
                    search_input = page.locator('input[placeholder="Cari..."]')
                    if search_input.count() == 0:
                        print("  Search input not found! Reloading page...")
                        page.goto(target_url)
                        wait_for_table_load(page)
                        search_input = page.locator('input[placeholder="Cari..."]')
                        
                    # Fill search input and press Enter
                    search_input.click()
                    search_input.fill("") # Clear input first
                    search_input.fill(email)
                    search_input.press("Enter")
                    
                    # Wait for results to load
                    wait_for_table_load(page)
                    
                    # Scrape current page and loop for next pages
                    page_num = 1
                    current_scraped = 0
                    
                    while True:
                        print(f"  Scraping page {page_num}...")
                        scraped_in_page = scrape_page(page, email, csv_writer)
                        current_scraped += scraped_in_page
                        csv_file.flush() # Flush data to disk immediately
                        
                        # Check if there is a next page button and if it is enabled
                        # The next button contains the SVG 'tabler-icon-chevron-right'
                        next_button = page.locator('button[aria-label="Go to next page"]')
                        
                        if next_button.count() > 0 and next_button.is_visible() and not next_button.is_disabled():
                            print(f"  Navigating to next page...")
                            next_button.click()
                            page_num += 1
                            wait_for_table_load(page)
                        else:
                            break
                            
                    total_scraped = current_scraped
                    
                    if total_scraped > 0:
                        print(f"  Finished search for {email}. Total scraped: {total_scraped} rows.")
                        success = True
                        break
                    else:
                        print(f"  Peringatan: Total baris yang terambil adalah 0 untuk {email}.")
                        first_row_text = page.locator("table tbody tr").first.text_content().lower() if page.locator("table tbody tr").count() > 0 else ""
                        is_genuine_no_data = "tidak ada data" in first_row_text or "empty" in first_row_text or "no data" in first_row_text
                        
                        if is_genuine_no_data:
                            print(f"  Tabel menunjukkan secara valid bahwa tidak ada data untuk {email}.")
                            
                        if attempt < attempts:
                            print(f"  Mencoba kembali 1 kali lagi untuk memastikan...")
                            try:
                                page.goto(target_url)
                                page.wait_for_selector("table", timeout=45000)
                            except Exception:
                                pass
                        else:
                            print(f"  Selesai mencari untuk {email} setelah {attempts} percobaan. Total scraped: {total_scraped} rows.")
                            success = True
                            
                except Exception as e:
                    print(f"  Error processing email {email} (Percobaan {attempt}/{attempts}): {e}")
                    if attempt < attempts:
                        print(f"  Mencoba kembali karena terjadi error...")
                        try:
                            page.goto(target_url)
                            page.wait_for_selector("table", timeout=45000)
                        except Exception:
                            pass
                    else:
                        print(f"  Gagal memproses email {email} setelah {attempts} percobaan.")
                # Optional: pause script to let user inspect
                # input("Press Enter to continue to next email...")
                
        # Close handles
        csv_file.close()
        browser.close()
        print(f"\nAll scraping completed! Data saved in '{output_csv}'")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    except Exception as e:
        print(f"\nFatal error: {e}")
