import os
import csv
import json
import shutil
import subprocess
from datetime import datetime, timezone, timedelta


# Capture execution start time (WITA is UTC+8)
wita_tz = timezone(timedelta(hours=8))
START_TIME = datetime.now(wita_tz)

def get_wita_timestamp():
    # Central Indonesian Time (WITA) is UTC+8
    now = START_TIME
    
    months = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
        7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    
    day = now.day
    month_name = months[now.month]
    year = now.year
    hour_minute = now.strftime("%H.%M")
    
    return f"{day} {month_name} {year} pukul {hour_minute} WITA"

def normalize_scale(scale_str):
    if not scale_str:
        return "Keluarga"
    
    s = scale_str.strip().upper()
    if not s or s == "-" or s == "TIDAK TERIDENTIFIKASI":
        return "Keluarga"
        
    if "DUMMY" in s:
        return "UMKM/Dummy"
        
    if "BANGUNAN_LAIN" in s or "BANGUNAN LAIN" in s:
        return "UMKM Bangunan Lain"
        
    if "KELUARGA" in s:
        if "UMKM" in s:
            return "UMKM/Keluarga"
        return "Keluarga"
        
    if "UMK" in s:
        return "UMK"
        
    if s == "UM":
        return "UM"
        
    if s == "UB":
        return "UB"
        
    if "UMKM" in s:
        return "UMKM/Keluarga"
        
    return "Keluarga"

def run_git_commands(timestamp_str):
    # Git push and GitHub actions are disabled as per user request
    print("Otomasi Git & Push ke GitHub dinonaktifkan.")
    return


def load_priority_sls():
    priority_file = os.path.join("data", "kdsls_prioritas.txt")
    if not os.path.exists(priority_file):
        print(f"Warning: Priority SLS file '{priority_file}' not found.")
        return set()
    try:
        with open(priority_file, "r", encoding="utf-8") as f:
            codes = {line.strip() for line in f if line.strip()}
        print(f"Loaded {len(codes)} priority SLS codes.")
        return codes
    except Exception as e:
        print(f"Error loading priority SLS codes: {e}")
        return set()

def load_muatan_wilkerstat():
    csv_file = "muatan_wilkerstat.csv"
    muatan_map = {}
    if not os.path.exists(csv_file):
        csv_file = os.path.join("data", "muatan_wilkerstat.csv")
    
    if os.path.exists(csv_file):
        try:
            with open(csv_file, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Find columns case-insensitively
                    sls_col = next((k for k in row.keys() if k.lower().strip() in ['kode_sls', 'idsls', 'sls_code']), None)
                    muatan_col = next((k for k in row.keys() if k.lower().strip() in ['muatan', 'capacity', 'target']), None)
                    ppl_col = next((k for k in row.keys() if k.lower().strip() in ['nama ppl', 'ppl', 'pencacah']), None)
                    pml_col = next((k for k in row.keys() if k.lower().strip() in ['pml', 'pengawas']), None)
                    
                    if sls_col:
                        sls_val = row[sls_col]
                        if sls_val:
                            sls_digits = "".join([c for c in str(sls_val) if c.isdigit()])
                            sls_16 = sls_digits[:16]
                            
                            muatan_val = 0
                            if muatan_col and row[muatan_col]:
                                try:
                                    muatan_val = int(row[muatan_col])
                                except ValueError:
                                    pass
                                    
                            ppl_name = ""
                            if ppl_col and row[ppl_col]:
                                ppl_name = row[ppl_col].strip()
                                
                            pml_name = ""
                            if pml_col and row[pml_col]:
                                pml_name = row[pml_col].strip()
                                
                            muatan_map[sls_16] = {
                                'muatan': muatan_val,
                                'ppl_name': ppl_name,
                                'pml_name': pml_name
                            }
            print(f"Loaded {len(muatan_map)} Wilkerstat SLS capacity mappings from CSV '{csv_file}'.")
            return muatan_map
        except Exception as e:
            print(f"Error loading Wilkerstat capacity from CSV: {e}")
            
    # Fallback to Excel
    excel_file = "muatan_wilkerstat.xlsx"
    if not os.path.exists(excel_file):
        excel_file = os.path.join("data", "muatan_wilkerstat.xlsx")
        
    if os.path.exists(excel_file):
        try:
            import pandas as pd
            df = pd.read_excel(excel_file)
            sls_col = next((c for c in df.columns if c.lower().strip() in ['kode_sls', 'idsls', 'sls_code']), None)
            muatan_col = next((c for c in df.columns if c.lower().strip() in ['muatan', 'capacity', 'target']), None)
            ppl_col = next((c for c in df.columns if c.lower().strip() in ['nama ppl', 'ppl', 'pencacah']), None)
            pml_col = next((c for c in df.columns if c.lower().strip() in ['pml', 'pengawas']), None)
            
            for _, row in df.iterrows():
                sls_val = row.get(sls_col) if sls_col else None
                if pd.notna(sls_val):
                    sls_digits = "".join([c for c in str(sls_val) if c.isdigit()])
                    sls_16 = sls_digits[:16]
                    
                    muatan_val = 0
                    if muatan_col and pd.notna(row.get(muatan_col)):
                        muatan_val = int(row[muatan_col])
                        
                    ppl_name = ""
                    if ppl_col and pd.notna(row.get(ppl_col)):
                        ppl_name = str(row[ppl_col]).strip()
                        
                    pml_name = ""
                    if pml_col and pd.notna(row.get(pml_col)):
                        pml_name = str(row[pml_col]).strip()
                        
                    muatan_map[sls_16] = {
                        'muatan': muatan_val,
                        'ppl_name': ppl_name,
                        'pml_name': pml_name
                    }
            print(f"Loaded {len(muatan_map)} Wilkerstat SLS capacity mappings from Excel.")
        except Exception as e:
            print(f"Error loading Wilkerstat capacity from Excel: {e}")
            
    return muatan_map

def normalize_name(name):
    if not name:
        return ""
    n = name.lower().strip()
    n = n.replace("yusuf tandi", "yusup tandi")
    return n

def process_dashboard_scraped_data(priority_sls=None):
    if priority_sls is None:
        priority_sls = load_priority_sls()
    scraped_file = "dashboard_scraped_data.csv"
    koseka_file = os.path.join("data", "koseka.csv")
    ppl_file = os.path.join("data", "email_ppl.csv")
    if not os.path.exists(ppl_file):
        ppl_file = "email_ppl.csv"
    pml_file = os.path.join("data", "email_pml.csv")
    if not os.path.exists(pml_file):
        pml_file = "email_pml.csv"
    
    print("\n" + "="*50)
    print("PROCESSING DASHBOARD SCRAPED DATA")
    print("="*50)
    
    if not os.path.exists(scraped_file):
        print(f"Error: Dashboard scraped file '{scraped_file}' not found. Cannot process.")
        return False
        
    if not os.path.exists(koseka_file):
        print(f"Error: Koseka mapping file '{koseka_file}' not found. Cannot process.")
        return False
        
    if not os.path.exists(ppl_file):
        print(f"Error: PPL email file '{ppl_file}' not found. Cannot process.")
        return False

    if not os.path.exists(pml_file):
        print(f"Error: PML email file '{pml_file}' not found. Cannot process.")
        return False

    # 1. Load subdistrict and Koseka mapping
    print(f"Loading subdistrict and Koseka mapping from '{koseka_file}'...")
    koseka_map = {}
    try:
        with open(koseka_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                kd_kec = row.get('kd_kec', '').strip()
                if kd_kec:
                    koseka_map[kd_kec] = {
                        'nama_kec': row.get('nama_kec', '').strip(),
                        'koseka': row.get('koseka', '').strip()
                    }
        print(f"Loaded {len(koseka_map)} subdistrict mappings.")
    except Exception as e:
        print(f"Error reading koseka file: {e}")
        return False

    # 2. Load PML and PPL email mappings
    ppl_email_to_name = {}
    ppl_name_to_email = {}
    try:
        with open(ppl_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('Nama PPL', '').strip()
                email = row.get('email', '').strip().lower()
                if email:
                    ppl_email_to_name[email] = name
                    ppl_name_to_email[normalize_name(name)] = email
        print(f"Loaded {len(ppl_email_to_name)} PPL email mappings.")
    except Exception as e:
        print(f"Error reading email_ppl file: {e}")
        return False

    pml_email_to_name = {}
    pml_name_to_email = {}
    try:
        with open(pml_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('pml', '').strip()
                email = row.get('email_pml', '').strip().lower()
                if email:
                    pml_email_to_name[email] = name
                    pml_name_to_email[normalize_name(name)] = email
        print(f"Loaded {len(pml_email_to_name)} PML email mappings.")
    except Exception as e:
        print(f"Error reading email_pml file: {e}")
        return False

    # 3. Load Wilkerstat capacity mapping
    wilkerstat_map = load_muatan_wilkerstat()
    if not wilkerstat_map:
        print("Error: Wilkerstat capacity map is empty. Cannot map dashboard data.")
        return False

    # 4. Read the raw scraped progress counts from existing dashboard_scraped_data.csv
    print(f"Loading raw scraped counts from '{scraped_file}'...")
    scraped_counts = {}
    try:
        with open(scraped_file, mode='r', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            try:
                headers = next(reader)
            except StopIteration:
                headers = []
            
            email_idx = 1
            sls_idx = 2
            cat_idx = 0
            
            # Find status column positions
            status_cols = ["OPEN", "DRAFT", "SUBMITTED BY Pencacah", "REJECTED BY Pengawas", "APPROVED BY Pengawas"]
            status_indices = {col: headers.index(col) if col in headers else -1 for col in status_cols}
            
            for row in reader:
                if not row or len(row) < 3:
                    continue
                cat = row[cat_idx].strip()
                email = row[email_idx].strip().lower()
                sls_code = row[sls_idx].strip()
                
                digits_only = "".join([c for c in sls_code if c.isdigit()])
                sls_16 = digits_only[:16]
                
                key = (cat.lower(), email, sls_16)
                
                counts = {}
                for col in status_cols:
                    idx = status_indices[col]
                    val = 0
                    if idx != -1 and idx < len(row):
                        try:
                            val = int(row[idx])
                        except ValueError:
                            pass
                    counts[col] = val
                
                scraped_counts[key] = counts
        print(f"Loaded {len(scraped_counts)} raw scraped status rows.")
    except Exception as e:
        print(f"Warning loading existing scraped counts: {e}")

    # 5. Build clean, aligned data based on Toraja Utara master list (wilkerstat_map)
    print("Aligning and building aligned dashboard rows...")
    aligned_rows = []
    
    # We output exactly the 14 headers:
    output_headers = [
        "Category", "Email", "SLS Code", 
        "OPEN", "DRAFT", "SUBMITTED BY Pencacah", "REJECTED BY Pengawas", "APPROVED BY Pengawas",
        "nama_petugas", "jabatan_petugas", "nama_kec", "koseka", "is_prioritas", "muatan_wilkerstat"
    ]
    
    for sls_16, details in wilkerstat_map.items():
        muatan = details['muatan']
        ppl_name = details['ppl_name']
        pml_name = details['pml_name']
        
        # Get emails from names
        ppl_email = ppl_name_to_email.get(normalize_name(ppl_name), "")
        pml_email = pml_name_to_email.get(normalize_name(pml_name), "")
        
        # Get subdistrict (kecamatan) mapping
        kd_kec_7 = sls_16[:7]
        nama_kec = ""
        koseka = ""
        if kd_kec_7 in koseka_map:
            nama_kec = koseka_map[kd_kec_7]['nama_kec']
            koseka = koseka_map[kd_kec_7]['koseka']
            
        # Get priority
        sls_14 = sls_16[:14]
        is_prioritas = "Ya" if sls_14 in priority_sls else "Tidak"
        
        # A. Create Pencacah row
        ppl_key = ('pencacah', ppl_email, sls_16)
        if ppl_key in scraped_counts:
            counts = scraped_counts[ppl_key]
        else:
            # Initialize with target capacity as OPEN
            counts = {
                "OPEN": muatan,
                "DRAFT": 0,
                "SUBMITTED BY Pencacah": 0,
                "REJECTED BY Pengawas": 0,
                "APPROVED BY Pengawas": 0
            }
        
        ppl_row = [
            "Pencacah", ppl_email, sls_16,
            str(counts["OPEN"]), str(counts["DRAFT"]), str(counts["SUBMITTED BY Pencacah"]),
            str(counts["REJECTED BY Pengawas"]), str(counts["APPROVED BY Pengawas"]),
            ppl_name, "PPL", nama_kec, koseka, is_prioritas, str(muatan)
        ]
        aligned_rows.append(ppl_row)
        
        # B. Create Pengawas row
        pml_key = ('pengawas', pml_email, sls_16)
        if pml_key in scraped_counts:
            counts = scraped_counts[pml_key]
        else:
            counts = {
                "OPEN": muatan,
                "DRAFT": 0,
                "SUBMITTED BY Pencacah": 0,
                "REJECTED BY Pengawas": 0,
                "APPROVED BY Pengawas": 0
            }
            
        pml_row = [
            "Pengawas", pml_email, sls_16,
            str(counts["OPEN"]), str(counts["DRAFT"]), str(counts["SUBMITTED BY Pencacah"]),
            str(counts["REJECTED BY Pengawas"]), str(counts["APPROVED BY Pengawas"]),
            pml_name, "PML", nama_kec, koseka, is_prioritas, str(muatan)
        ]
        aligned_rows.append(pml_row)
        
    # Write clean aligned data back to dashboard_scraped_data.csv
    try:
        with open(scraped_file, mode='w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(output_headers)
            writer.writerows(aligned_rows)
        print(f"Successfully aligned and saved '{scraped_file}' with {len(aligned_rows)} rows.")
        generate_local_dashboard()
        return True
    except Exception as e:
        print(f"Error writing aligned dashboard scraped data: {e}")
        return False

def process_data():
    scraped_file = "scraped_data.csv"
    koseka_file = os.path.join("data", "koseka.csv")
    output_file = "update_data.csv"
    
    print("\n" + "="*50)
    print("STARTING DATA PROCESSING PIPELINE")
    print("="*50)
    
    if not os.path.exists(scraped_file):
        print(f"Error: Scraped data file '{scraped_file}' not found. Cannot process.")
        return False
        
    if not os.path.exists(koseka_file):
        print(f"Error: Koseka mapping file '{koseka_file}' not found. Cannot process.")
        return False
        
    # Load priority SLS codes
    priority_sls = load_priority_sls()

    # 1. Load subdistrict and Koseka mapping
    print(f"Loading subdistrict and Koseka mapping from '{koseka_file}'...")
    koseka_map = {}
    try:
        with open(koseka_file, mode='r', encoding='utf-8') as f:
            # Semicolon delimited
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                kd_kec = row.get('kd_kec', '').strip()
                if kd_kec:
                    koseka_map[kd_kec] = {
                        'nama_kec': row.get('nama_kec', '').strip(),
                        'koseka': row.get('koseka', '').strip()
                    }
        print(f"Loaded {len(koseka_map)} subdistrict mappings.")
    except Exception as e:
        print(f"Error reading koseka file: {e}")
        return False

    # Load Wilkerstat capacity mapping for Toraja Utara
    wilkerstat_map = load_muatan_wilkerstat()

    # 2. Process scraped_data.csv and merge with existing output_file
    print(f"Processing, mapping, and merging '{scraped_file}'...")
    rows_written = 0
    try:
        # Load existing data from update_data.csv if it exists
        existing_data = {}
        headers = []
        id_code_idx = 1
        
        if os.path.exists(output_file):
            print(f"Found existing '{output_file}'. Loading data for merging...")
            try:
                with open(output_file, mode='r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    try:
                        headers = next(reader)
                        if 'Kode Identitas' in headers:
                            id_code_idx = headers.index('Kode Identitas')
                        else:
                            id_code_idx = 1
                    except StopIteration:
                        headers = []
                    
                    for row in reader:
                        if not row or len(row) <= id_code_idx:
                            continue
                        id_code = row[id_code_idx].strip()
                        if id_code:
                            digits_only = "".join([c for c in id_code if c.isdigit()])
                            sls_16 = digits_only[:16]
                            if wilkerstat_map and sls_16 not in wilkerstat_map:
                                continue # Filter out Sangihe or other non-Toraja Utara SLS codes
                            
                            if len(row) > 7:
                                row[7] = normalize_scale(row[7])
                            existing_data[id_code] = row
                print(f"Loaded {len(existing_data)} existing records from '{output_file}' (filtered for Toraja Utara).")
            except Exception as e:
                print(f"Warning: Could not read existing output file for merging: {e}")
        
        # Read new scraped data
        with open(scraped_file, mode='r', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            try:
                new_headers = next(reader)
                headers = new_headers + ['nama_kec', 'koseka', 'is_prioritas']
                if 'Kode Identitas' in new_headers:
                    new_id_code_idx = new_headers.index('Kode Identitas')
                else:
                    new_id_code_idx = 1
            except StopIteration:
                print("Error: scraped_data.csv is empty.")
                return False
            
            new_rows_count = 0
            updated_rows_count = 0
            for row in reader:
                if not row or len(row) <= new_id_code_idx:
                    continue
                
                id_code = row[new_id_code_idx].strip()
                if not id_code:
                    continue  # Skip empty/invalid identity codes
                
                digits_only = "".join([c for c in id_code if c.isdigit()])
                sls_16 = digits_only[:16]
                if wilkerstat_map and sls_16 not in wilkerstat_map:
                    continue # Skip non-Toraja Utara
                
                if len(row) > 7:
                    row[7] = normalize_scale(row[7])
                
                # Extract digits to match with kd_kec
                kd_kec_7 = digits_only[:7]
                
                nama_kec = ""
                koseka = ""
                if kd_kec_7 in koseka_map:
                    nama_kec = koseka_map[kd_kec_7]['nama_kec']
                    koseka = koseka_map[kd_kec_7]['koseka']
                
                # We will process is_prioritas when writing all rows
                mapped_row = row + [nama_kec, koseka]
                
                if id_code in existing_data:
                    updated_rows_count += 1
                else:
                    new_rows_count += 1
                
                existing_data[id_code] = mapped_row
                
        print(f"Scraped data processed: {updated_rows_count} records updated, {new_rows_count} new records added (filtered for Toraja Utara).")
        
        # Prepare list of rows to write and normalize columns to exactly 19 (16 base + 3 extra)
        rows_to_write = []
        for id_code, row in existing_data.items():
            base_row = row[:16]
            while len(base_row) < 16:
                base_row.append("")
                
            digits_only = "".join([c for c in id_code if c.isdigit()])
            kd_kec_7 = digits_only[:7]
            sls_14 = digits_only[:14]
            
            nama_kec = ""
            koseka = ""
            if kd_kec_7 in koseka_map:
                nama_kec = koseka_map[kd_kec_7]['nama_kec']
                koseka = koseka_map[kd_kec_7]['koseka']
                
            is_prioritas = "Ya" if sls_14 in priority_sls else "Tidak"
            rows_to_write.append(base_row + [nama_kec, koseka, is_prioritas])
        
        # Write merged/updated records back to update_data.csv
        with open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(headers)
            writer.writerows(rows_to_write)
            
        rows_written = len(rows_to_write)
        print(f"Successfully merged and created '{output_file}' with {rows_written} rows.")
        
        # Also write the merged raw data back to scraped_data.csv (excluding the last three columns: nama_kec, koseka, is_prioritas)
        raw_headers = headers[:-3] if len(headers) > 3 else headers
        raw_rows = [row[:-3] if len(row) > 3 else row for row in rows_to_write]
        
        with open(scraped_file, mode='w', newline='', encoding='utf-8') as sf:
            writer = csv.writer(sf)
            writer.writerow(raw_headers)
            writer.writerows(raw_rows)
        print(f"Successfully updated '{scraped_file}' with {len(raw_rows)} merged rows.")
        
    except Exception as e:
        print(f"Error mapping and merging scraped data: {e}")
        return False

    # 2b. Process dashboard scraped data
    process_dashboard_scraped_data(priority_sls)

    # 3. Copy to Next.js dashboard public folder & write timestamp
    public_dir = os.path.join("dashboard", "public")
    if os.path.exists(public_dir):
        print(f"Copying files to dashboard public directory...")
        try:
            # Copy CSV
            shutil.copy2(output_file, os.path.join(public_dir, "update_data.csv"))
            print(f"Copied '{output_file}' to dashboard public folder.")
            
            # Copy dashboard_scraped_data.csv
            dashboard_scraped_src = "dashboard_scraped_data.csv"
            if os.path.exists(dashboard_scraped_src):
                shutil.copy2(dashboard_scraped_src, os.path.join(public_dir, "dashboard_scraped_data.csv"))
                print(f"Copied '{dashboard_scraped_src}' to dashboard public folder.")
            
            # Copy PML PPL CSV
            pml_ppl_src = os.path.join("data", "pml_ppl.csv")
            if os.path.exists(pml_ppl_src):
                shutil.copy2(pml_ppl_src, os.path.join(public_dir, "pml_ppl.csv"))
                print(f"Copied '{pml_ppl_src}' to dashboard public folder.")
            
            # Copy ringkasan_Assign.csv
            assign_src = os.path.join("data", "ringkasan_Assign.csv")
            if os.path.exists(assign_src):
                shutil.copy2(assign_src, os.path.join(public_dir, "ringkasan_Assign.csv"))
                print(f"Copied '{assign_src}' to dashboard public folder.")
            
            # Copy ringkasan_Progres.csv
            progres_src = os.path.join("data", "ringkasan_Progres.csv")
            if os.path.exists(progres_src):
                shutil.copy2(progres_src, os.path.join(public_dir, "ringkasan_Progres.csv"))
                print(f"Copied '{progres_src}' to dashboard public folder.")
            
            # Generate and write timestamp
            timestamp = get_wita_timestamp()
            timestamp_file = os.path.join(public_dir, "last_updated.txt")
            with open(timestamp_file, "w", encoding="utf-8") as tf:
                tf.write(timestamp)
            print(f"Wrote timestamp '{timestamp}' to '{timestamp_file}'.")
            
            # Trigger Git automation
            run_git_commands(timestamp)
            
        except Exception as copy_err:
            print(f"Warning: Could not copy files to dashboard public folder or push to Git: {copy_err}")
    else:
        print(f"Warning: Dashboard public directory '{public_dir}' not found. Skipping copy and git push.")
        
    print("="*50 + "\n")
    return True

def generate_local_dashboard():
    scraped_file = "dashboard_scraped_data.csv"
    assign_file = os.path.join("data", "ringkasan_Assign.csv")
    progres_file = os.path.join("data", "ringkasan_Progres.csv")
    output_html = "index.html"
    
    print("\n" + "="*50)
    print("MENGHASILKAN DASHBOARD LOKAL HTML")
    print("="*50)
    
    # 1. Load dashboard scraped data
    scraped_data = []
    if os.path.exists(scraped_file):
        try:
            with open(scraped_file, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Clean and parse numeric values
                    for col in ["OPEN", "DRAFT", "SUBMITTED BY Pencacah", "REJECTED BY Pengawas", "APPROVED BY Pengawas", "muatan_wilkerstat"]:
                        if col in row:
                            try:
                                row[col] = int(row[col])
                            except ValueError:
                                row[col] = 0
                    scraped_data.append(row)
            print(f"Berhasil memuat {len(scraped_data)} baris data dari '{scraped_file}'")
        except Exception as e:
            print(f"Peringatan: Gagal memuat '{scraped_file}': {e}")
            
    # 1b. Load PML PPL map to fill name and role for missing emails
    pml_ppl_file = os.path.join("data", "pml_ppl.csv")
    pml_ppl_map = {}
    if os.path.exists(pml_ppl_file):
        try:
            with open(pml_ppl_file, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=',')
                for row in reader:
                    email = row.get('email', '').strip().lower()
                    if email:
                        pml_ppl_map[email] = {
                            'nama_petugas': row.get('nama_petugas', '').strip(),
                            'jabatan_petugas': row.get('jabatan_petugas', '').strip(),
                            'kec': row.get('kec', '').strip()
                        }
        except Exception as e:
            print(f"Peringatan: Gagal memuat '{pml_ppl_file}' di generator: {e}")

    # 1c. Load all registered emails from email_mitra.txt
    email_file = os.path.join("data", "email_mitra.txt")
    if not os.path.exists(email_file):
        email_file = os.path.join("data", "email_mitra_test.txt")
        
    registered_emails = []
    if os.path.exists(email_file):
        try:
            with open(email_file, "r", encoding="utf-8") as ef:
                registered_emails = [line.strip().lower() for line in ef if line.strip()]
            print(f"Memuat {len(registered_emails)} email mitra terdaftar untuk pemeriksaan keaktifan.")
        except Exception as e:
            print(f"Peringatan: Gagal memuat file email mitra: {e}")

    # 1d. Fill in 0 progress data for registered emails that are missing in scraped data
    scraped_emails_set = set(row.get("Email", "").strip().lower() for row in scraped_data if row.get("Email"))
    
    missing_count = 0
    for email in registered_emails:
        if email not in scraped_emails_set:
            nama_petugas = ""
            jabatan_petugas = ""
            nama_kec = ""
            if email in pml_ppl_map:
                nama_petugas = pml_ppl_map[email]['nama_petugas']
                jabatan_petugas = pml_ppl_map[email]['jabatan_petugas']
                nama_kec = pml_ppl_map[email].get('kec', '')
                
            category = "Pencacah"
            if jabatan_petugas == "PML":
                category = "Pengawas"
                
            blank_row = {
                "Category": category,
                "Email": email,
                "SLS Code": "",
                "OPEN": 0,
                "DRAFT": 0,
                "SUBMITTED BY Pencacah": 0,
                "REJECTED BY Pengawas": 0,
                "APPROVED BY Pengawas": 0,
                "nama_petugas": nama_petugas,
                "jabatan_petugas": jabatan_petugas,
                "nama_kec": nama_kec,
                "koseka": "",
                "is_prioritas": "Tidak",
                "muatan_wilkerstat": 0
            }
            scraped_data.append(blank_row)
            missing_count += 1
            
    if missing_count > 0:
        print(f"Menambahkan {missing_count} email terdaftar yang tidak memiliki penugasan/progress (bernilai 0).")
            
    # 2. Load ringkasan assign
    assign_data = {}
    if os.path.exists(assign_file):
        try:
            with open(assign_file, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    assign_data = rows[0]
                    # Convert values to int
                    for k, v in assign_data.items():
                        try:
                            assign_data[k] = int(v)
                        except ValueError:
                            pass
            print(f"Berhasil memuat ringkasan target (Assign): {assign_data}")
        except Exception as e:
            print(f"Peringatan: Gagal memuat '{assign_file}': {e}")
            
    # 3. Load ringkasan progres
    progres_data = {}
    if os.path.exists(progres_file):
        try:
            with open(progres_file, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    progres_data = rows[0]
                    # Convert values to int
                    for k, v in progres_data.items():
                        try:
                            progres_data[k] = int(v)
                        except ValueError:
                            pass
            print(f"Berhasil memuat ringkasan progres: {progres_data}")
        except Exception as e:
            print(f"Peringatan: Gagal memuat '{progres_file}': {e}")

    # Fallbacks if ringkasan is missing
    if not progres_data and scraped_data:
        progres_data = {
            "OPEN": sum(r.get("OPEN", 0) for r in scraped_data),
            "DRAFT": sum(r.get("DRAFT", 0) for r in scraped_data),
            "SUBMITTED BY Pencacah": sum(r.get("SUBMITTED BY Pencacah", 0) for r in scraped_data),
            "REJECTED BY Pengawas": sum(r.get("REJECTED BY Pengawas", 0) for r in scraped_data),
            "APPROVED BY Pengawas": sum(r.get("APPROVED BY Pengawas", 0) for r in scraped_data),
        }
    if not assign_data and scraped_data:
        total_sls = len(set(r.get("SLS Code") for r in scraped_data if r.get("SLS Code")))
        assign_data = {
            "assigned": total_sls,
            "have-not-assigned": 0
        }

    # Get timestamp
    timestamp = get_wita_timestamp()
    
    # 4. Generate HTML content
    template = get_dashboard_html_template()
    html_content = template.replace("__SCRAPED_DATA_JSON__", json.dumps(scraped_data))
    html_content = html_content.replace("__ASSIGN_DATA_JSON__", json.dumps(assign_data))
    html_content = html_content.replace("__PROGRES_DATA_JSON__", json.dumps(progres_data))
    html_content = html_content.replace("__TIMESTAMP__", timestamp)
    
    try:
        with open(output_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Berhasil memperbarui dashboard lokal di '{output_html}'")
        return True
    except Exception as e:
        print(f"Error menulis file dashboard HTML: {e}")
        return False

def get_dashboard_html_template():
    return r"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Toraja Utara - Sensus Ekonomi 2026</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #ea580c;       /* Sensus Ekonomi 2026 Orange */
            --primary-light: #f97316; /* Lighter Orange */
            --primary-bg: #fff7ed;    /* Light Orange Background tint */
            --background: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
            
            --color-open: #64748b;
            --color-draft: #b45309;
            --color-submitted: #0284c7;
            --color-rejected: #e11d48;
            --color-approved: #16a34a;
            
            --radius-sm: 6px;
            --radius-md: 10px;
            --radius-lg: 16px;
            
            --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.05);
            --shadow-md: 0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.08);
            --transition: all 0.2s ease-in-out;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--background);
            color: var(--text-main);
            line-height: 1.6;
            padding: 2rem 1.5rem;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        /* Header CSS */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            flex-wrap: wrap;
            gap: 1rem;
        }

        .logo-section h1 {
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--primary);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .logo-section p {
            color: var(--text-muted);
            font-size: 0.875rem;
            margin-top: 0.25rem;
        }

        .meta-section {
            text-align: right;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 0.5rem;
        }

        .badge-local {
            background-color: #f1f5f9;
            color: #475569;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            border: 1px solid #cbd5e1;
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }

        .last-update {
            font-size: 0.8125rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }

        /* KPI Cards Grid */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }

        .kpi-card {
            background-color: var(--card-bg);
            border-radius: var(--radius-md);
            padding: 1.5rem;
            box-shadow: var(--shadow);
            border: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: var(--transition);
        }

        .kpi-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }

        .kpi-card.progress-card {
            background: linear-gradient(135deg, var(--primary), #f97316);
            color: white;
            grid-column: span 2;
        }

        @media (max-width: 768px) {
            .kpi-card.progress-card {
                grid-column: span 1;
            }
        }

        .kpi-title {
            font-size: 0.8125rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            font-weight: 600;
            margin-bottom: 0.5rem;
            min-height: 2.25rem;
        }

        .progress-card .kpi-title {
            color: rgba(255, 255, 255, 0.85);
        }

        .kpi-value {
            font-size: 1.875rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }

        .progress-card .kpi-value {
            font-size: 2.25rem;
        }

        .progress-wrapper {
            margin-top: 0.5rem;
        }

        .progress-bar-bg {
            background-color: rgba(255, 255, 255, 0.2);
            border-radius: 9999px;
            height: 10px;
            width: 100%;
            overflow: hidden;
        }

        .progress-bar-fill {
            background-color: #38bdf8;
            height: 100%;
            border-radius: 9999px;
            width: 0%;
            transition: width 1s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .progress-info {
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            margin-top: 0.35rem;
            color: rgba(255, 255, 255, 0.9);
        }

        .kpi-indicator {
            display: flex;
            align-items: center;
            gap: 0.35rem;
            font-size: 0.8125rem;
            font-weight: 500;
        }

        .indicator-open { color: var(--color-open); }
        .indicator-draft { color: var(--color-draft); }
        .indicator-submitted { color: var(--color-submitted); }
        .indicator-rejected { color: var(--color-rejected); }
        .indicator-approved { color: var(--color-approved); }

        .kpi-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }
        .bg-open { background-color: var(--color-open); }
        .bg-draft { background-color: var(--color-draft); }
        .bg-submitted { background-color: var(--color-submitted); }
        .bg-rejected { background-color: var(--color-rejected); }
        .bg-approved { background-color: var(--color-approved); }

        /* Filter Controls */
        .controls-card {
            background-color: var(--card-bg);
            border-radius: var(--radius-md);
            padding: 1.5rem;
            box-shadow: var(--shadow);
            border: 1px solid var(--border);
            margin-bottom: 2rem;
        }

        .controls-grid {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr auto;
            gap: 1rem;
            align-items: flex-end;
        }

        @media (max-width: 1024px) {
            .controls-grid {
                grid-template-columns: 1fr 1fr;
            }
            .controls-grid .btn-clear {
                grid-column: span 2;
            }
        }

        @media (max-width: 640px) {
            .controls-grid {
                grid-template-columns: 1fr;
            }
            .controls-grid .btn-clear {
                grid-column: span 1;
            }
        }

        .control-group {
            display: flex;
            flex-direction: column;
            gap: 0.375rem;
        }

        .control-label {
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
        }

        .control-input {
            width: 100%;
            padding: 0.625rem 0.875rem;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
            background-color: #fff;
            color: var(--text-main);
            font-family: inherit;
            font-size: 0.875rem;
            outline: none;
            transition: var(--transition);
        }

        .control-input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(234, 88, 12, 0.15);
        }

        .btn-clear {
            padding: 0.625rem 1.25rem;
            background-color: #f1f5f9;
            border: 1px solid var(--border);
            color: #475569;
            font-size: 0.875rem;
            font-weight: 600;
            border-radius: var(--radius-sm);
            cursor: pointer;
            transition: var(--transition);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.35rem;
            height: 38px;
        }

        .btn-clear:hover {
            background-color: #e2e8f0;
            color: var(--text-main);
        }

        /* Tabs Container */
        .tabs-header {
            display: flex;
            border-bottom: 2px solid var(--border);
            margin-bottom: 1.5rem;
            gap: 1.5rem;
            flex-wrap: wrap;
        }

        .tab-btn {
            padding: 0.75rem 0.5rem;
            background: none;
            border: none;
            border-bottom: 3px solid transparent;
            color: var(--text-muted);
            font-size: 0.9375rem;
            font-weight: 600;
            cursor: pointer;
            transition: var(--transition);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .tab-btn:hover {
            color: var(--primary);
        }

        .tab-btn.active {
            color: var(--primary);
            border-bottom-color: var(--primary);
        }

        /* Data Tables styling */
        .table-card {
            background-color: var(--card-bg);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow);
            border: 1px solid var(--border);
            overflow: hidden;
            margin-bottom: 1.5rem;
        }

        .table-responsive {
            width: 100%;
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.875rem;
        }

        th {
            background-color: #f8fafc;
            color: #475569;
            font-weight: 600;
            padding: 0.875rem 1.25rem;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
            cursor: pointer;
            user-select: none;
            transition: var(--transition);
        }

        th:hover {
            background-color: #f1f5f9;
        }

        th.no-sort {
            cursor: default;
        }

        th.no-sort:hover {
            background-color: #f8fafc;
        }

        td {
            padding: 1rem 1.25rem;
            border-bottom: 1px solid var(--border);
            color: #334155;
            white-space: nowrap;
        }

        tr:last-child td {
            border-bottom: none;
        }

        tr:hover td {
            background-color: #f8fafc;
        }

        .sort-indicator {
            margin-left: 0.25rem;
            display: inline-block;
            font-size: 0.65rem;
            color: var(--text-muted);
        }

        /* Progress Bar Cell */
        .progress-cell {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            min-width: 150px;
        }

        .progress-bar-cell-bg {
            background-color: #e2e8f0;
            border-radius: 9999px;
            height: 6px;
            flex-grow: 1;
            overflow: hidden;
        }

        .progress-bar-cell-fill {
            background-color: var(--primary);
            height: 100%;
            border-radius: 9999px;
        }

        .progress-percent-text {
            font-weight: 600;
            font-size: 0.75rem;
            width: 38px;
            text-align: right;
        }

        /* Status Badges */
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 0.125rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            border: 1px solid transparent;
        }

        .badge-priority {
            background-color: #fffbeb;
            color: #b45309;
            border-color: #fde68a;
        }

        .badge-non-priority {
            background-color: #f1f5f9;
            color: #475569;
            border-color: #cbd5e1;
        }

        .badge-role {
            background-color: #eff6ff;
            color: #1d4ed8;
            border-color: #bfdbfe;
        }

        /* Pagination style */
        .pagination-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 1.5rem;
            border-top: 1px solid var(--border);
            background-color: #f8fafc;
            flex-wrap: wrap;
            gap: 1rem;
        }

        .pagination-info {
            font-size: 0.8125rem;
            color: var(--text-muted);
        }

        .pagination-controls {
            display: flex;
            gap: 0.25rem;
            align-items: center;
        }

        .page-btn {
            min-width: 32px;
            height: 32px;
            padding: 0 0.5rem;
            border: 1px solid var(--border);
            background-color: #fff;
            color: var(--text-main);
            font-weight: 500;
            font-size: 0.8125rem;
            border-radius: var(--radius-sm);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: var(--transition);
        }

        .page-btn:hover:not(:disabled) {
            border-color: var(--primary);
            color: var(--primary);
            background-color: var(--primary-bg);
        }

        .page-btn.active {
            background-color: var(--primary);
            color: #fff;
            border-color: var(--primary);
        }

        .page-btn:disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }

        /* Table empty state */
        .empty-state {
            padding: 3rem;
            text-align: center;
            color: var(--text-muted);
        }

        .empty-state svg {
            margin-bottom: 1rem;
            color: #cbd5e1;
        }

        /* Footer styling */
        footer {
            margin-top: 3rem;
            text-align: center;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 0.8125rem;
        }

        /* Highlights */
        .txt-open { color: var(--color-open); font-weight: 600; }
        .txt-draft { color: var(--color-draft); font-weight: 600; }
        .txt-submitted { color: var(--color-submitted); font-weight: 600; }
        .txt-rejected { color: var(--color-rejected); font-weight: 600; }
        .txt-approved { color: var(--color-approved); font-weight: 600; }

        /* Animation skeleton keyframes */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .animated-tab {
            animation: fadeIn 0.25s ease-out forwards;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="logo-section">
                <h1>
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--primary)">
                        <path d="M3 3v18h18"/>
                        <path d="m19 9-5 5-4-4-3 3"/>
                    </svg>
                    TORAJA UTARA - SENSUS EKONOMI 2026
                </h1>
                <p>Dashboard Monitoring Progress Lapangan - Hasil Scraping FASIH</p>
            </div>
            
            <div class="meta-section">
                <div class="badge-local">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="m9 12 2 2 4-4"/>
                    </svg>
                    Lokal (Tanpa Sinkronisasi GitHub)
                </div>
                <div class="last-update" id="lastUpdatedContainer">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
                    </svg>
                    Terakhir Diperbarui: <strong id="timestampText">__TIMESTAMP__</strong>
                </div>
            </div>
        </header>

        <!-- KPI Grid -->
        <div class="kpi-grid">
            <div class="kpi-card progress-card">
                <div>
                    <div class="kpi-title">Penyelesaian Progress</div>
                    <div class="kpi-value" id="kpiProgressPct">0.00%</div>
                </div>
                <div class="progress-wrapper">
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" id="kpiProgressBar"></div>
                    </div>
                    <div class="progress-info">
                        <span id="kpiProgressRatio">0 / 0 SLS</span>
                        <span id="kpiProgressText">Approved + Submitted + Rejected</span>
                    </div>
                </div>
            </div>

            <div class="kpi-card">
                <div>
                    <div class="kpi-title">Total Target SLS</div>
                    <div class="kpi-value" id="kpiTotalSLS">0</div>
                </div>
                <div class="kpi-indicator" style="color: var(--text-muted)">
                    Jumlah SLS Terpetakan
                </div>
            </div>

            <div class="kpi-card">
                <div>
                    <div class="kpi-title">Total Muatan</div>
                    <div class="kpi-value" id="kpiTotalMuatan">0</div>
                </div>
                <div class="kpi-indicator" style="color: var(--text-muted)">
                    Target Rincian Usaha
                </div>
            </div>

            <div class="kpi-card">
                <div>
                    <div class="kpi-title">Total Muatan Wilkerstat</div>
                    <div class="kpi-value" id="kpiTotalWilkerstat">0</div>
                </div>
                <div class="kpi-indicator" style="color: var(--text-muted)">
                    Muatan Wilkerstat Keseluruhan
                </div>
            </div>

            <div class="kpi-card">
                <div>
                    <div class="kpi-title">APPROVED PML</div>
                    <div class="kpi-value txt-approved" id="kpiApproved">0</div>
                </div>
                <div class="kpi-indicator indicator-approved">
                    <span class="kpi-dot bg-approved"></span> Bersih / Selesai
                </div>
            </div>

            <div class="kpi-card">
                <div>
                    <div class="kpi-title">SUBMITTED PPL</div>
                    <div class="kpi-value txt-submitted" id="kpiSubmitted">0</div>
                </div>
                <div class="kpi-indicator indicator-submitted">
                    <span class="kpi-dot bg-submitted"></span> Perlu Diperiksa
                </div>
            </div>

            <div class="kpi-card">
                <div>
                    <div class="kpi-title">DRAFT PPL</div>
                    <div class="kpi-value txt-draft" id="kpiDraft">0</div>
                </div>
                <div class="kpi-indicator indicator-draft">
                    <span class="kpi-dot bg-draft"></span> Sedang Dikerjakan
                </div>
            </div>

            <div class="kpi-card">
                <div>
                    <div class="kpi-title">OPEN</div>
                    <div class="kpi-value txt-open" id="kpiOpen">0</div>
                </div>
                <div class="kpi-indicator indicator-open">
                    <span class="kpi-dot bg-open"></span> Belum Disentuh
                </div>
            </div>

            <div class="kpi-card">
                <div>
                    <div class="kpi-title">REJECTED PML</div>
                    <div class="kpi-value txt-rejected" id="kpiRejected">0</div>
                </div>
                <div class="kpi-indicator indicator-rejected">
                    <span class="kpi-dot bg-rejected"></span> Perlu Perbaikan
                </div>
            </div>
        </div>

        <!-- Controls Form -->
        <div class="controls-card">
            <div class="controls-grid">
                <div class="control-group">
                    <label class="control-label" for="searchInput">Pencarian Cepat</label>
                    <input type="text" id="searchInput" class="control-input" placeholder="Cari Kode SLS, Nama Petugas, Email, Kecamatan, Koseka...">
                </div>

                <div class="control-group">
                    <label class="control-label" for="filterKec">Kecamatan</label>
                    <select id="filterKec" class="control-input">
                        <option value="">Semua Kecamatan</option>
                    </select>
                </div>

                <div class="control-group">
                    <label class="control-label" for="filterCategory">Peran Petugas</label>
                    <select id="filterCategory" class="control-input">
                        <option value="">Semua Peran</option>
                        <option value="PML">PML</option>
                        <option value="PPL">PPL</option>
                    </select>
                </div>

                <div class="control-group">
                    <label class="control-label" for="filterPriority">Prioritas SLS</label>
                    <select id="filterPriority" class="control-input">
                        <option value="">Semua SLS</option>
                        <option value="Ya">SLS Prioritas</option>
                        <option value="Tidak">Bukan Prioritas</option>
                    </select>
                </div>

                <button class="btn-clear" id="btnClearFilters">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M18 6 6 18M6 6l12 12"/>
                    </svg>
                    Reset Filter
                </button>
            </div>
        </div>

        <!-- Tabs Navigation -->
        <div class="tabs-header">
            <button class="tab-btn active" onclick="switchTab('kecamatan')">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/>
                    <circle cx="12" cy="10" r="3"/>
                </svg>
                Rekap Kecamatan
            </button>
            <button class="tab-btn" onclick="switchTab('petugas')">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
                    <circle cx="9" cy="7" r="4"/>
                    <path d="M22 21v-2a4 4 0 0 0-3-3.87"/>
                    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                </svg>
                Kinerja Petugas
            </button>
            <button class="tab-btn" onclick="switchTab('detail')">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M3 12h18M3 6h18M3 18h18"/>
                </svg>
                Tabulasi Detail SLS
            </button>
        </div>

        <!-- Dynamic Content Tables -->
        <div id="tabContentContainer">
            <!-- Table content will be injected by JS -->
        </div>

        <!-- Footer -->
        <footer>
            <p>Sensus Ekonomi 2026 Dashboard - Dihasilkan Secara Lokal oleh Antigravity AI Coding Assistant.</p>
        </footer>
    </div>

    <!-- Data Injection Placeholders -->
    <script>
        const rawScrapedData = __SCRAPED_DATA_JSON__;
        const assignData = __ASSIGN_DATA_JSON__;
        const progresData = __PROGRES_DATA_JSON__;
    </script>

    <!-- Main Logic JS -->
    <script>
        // Helper to normalize category/role to PPL or PML
        function getNormalizedRole(row) {
            const jab = (row.jabatan_petugas || '').toUpperCase();
            const cat = (row.Category || '').toUpperCase();
            if (jab === 'PML' || cat === 'PENGAWAS') return 'PML';
            if (jab === 'PPL' || cat === 'PENCACAH') return 'PPL';
            return 'PPL'; // Fallback
        }

        // Global variables state
        let currentTab = 'kecamatan';
        let searchQuery = '';
        let filterKec = '';
        let filterCategory = '';
        let filterPriority = '';
        
        // Sorting states
        let sortKecField = 'nama_kec';
        let sortKecAsc = true;
        let sortPetField = 'nama_petugas';
        let sortPetAsc = true;
        let sortDetField = 'SLS Code';
        let sortDetAsc = true;

        // Numeric fields to default sort descending on first click
        const numericFields = [
            'total_sls', 'muatan', 'OPEN', 'DRAFT', 'SUBMITTED', 'REJECTED', 'APPROVED', 'progress_rate',
            'muatan_wilkerstat', 'SUBMITTED BY Pencacah', 'REJECTED BY Pengawas', 'APPROVED BY Pengawas'
        ];
        
        // Pagination state for Detail SLS
        let detailCurrentPage = 1;
        let detailItemsPerPage = 25;

        // On document load
        document.addEventListener('DOMContentLoaded', () => {
            initFilters();
            calculateAndRenderKPIs();
            renderActiveTab();
            
            // Register input events
            document.getElementById('searchInput').addEventListener('input', (e) => {
                searchQuery = e.target.value;
                detailCurrentPage = 1;
                renderActiveTab();
            });
            
            document.getElementById('filterKec').addEventListener('change', (e) => {
                filterKec = e.target.value;
                detailCurrentPage = 1;
                renderActiveTab();
            });
            
            document.getElementById('filterCategory').addEventListener('change', (e) => {
                filterCategory = e.target.value;
                detailCurrentPage = 1;
                renderActiveTab();
            });
            
            document.getElementById('filterPriority').addEventListener('change', (e) => {
                filterPriority = e.target.value;
                detailCurrentPage = 1;
                renderActiveTab();
            });
            
            document.getElementById('btnClearFilters').addEventListener('click', () => {
                document.getElementById('searchInput').value = '';
                document.getElementById('filterKec').value = '';
                document.getElementById('filterCategory').value = '';
                document.getElementById('filterPriority').value = '';
                
                searchQuery = '';
                filterKec = '';
                filterCategory = '';
                filterPriority = '';
                detailCurrentPage = 1;
                renderActiveTab();
            });
        });

        // Initialize Filter Dropdowns
        function initFilters() {
            const selectKec = document.getElementById('filterKec');
            
            // Get unique kecamatan from data
            const kecSet = new Set();
            rawScrapedData.forEach(row => {
                const kecName = row.nama_kec || '';
                if (kecName && kecName.trim() !== '' && kecName.trim() !== 'TIDAK TERIDENTIFIKASI') {
                    kecSet.add(kecName.trim());
                }
            });
            
            // Sort and populate
            const sortedKec = Array.from(kecSet).sort();
            sortedKec.forEach(kec => {
                const opt = document.createElement('option');
                opt.value = kec;
                opt.textContent = kec;
                selectKec.appendChild(opt);
            });
        }

        // Calculate KPI values
        function calculateAndRenderKPIs() {
            // Aggregate counters from the raw dataset, but only count each SLS Code once
            const uniqueSlsMap = new Map();
            
            rawScrapedData.forEach(row => {
                const slsCode = row["SLS Code"];
                if (slsCode) {
                    if (!uniqueSlsMap.has(slsCode)) {
                        uniqueSlsMap.set(slsCode, {
                            OPEN: parseInt(row.OPEN) || 0,
                            DRAFT: parseInt(row.DRAFT) || 0,
                            SUBMITTED: parseInt(row["SUBMITTED BY Pencacah"]) || 0,
                            REJECTED: parseInt(row["REJECTED BY Pengawas"]) || 0,
                            APPROVED: parseInt(row["APPROVED BY Pengawas"]) || 0,
                            muatan: parseInt(row.muatan_wilkerstat) || 0
                        });
                    }
                }
            });
            
            let totalOpen = 0;
            let totalDraft = 0;
            let totalSubmitted = 0;
            let totalRejected = 0;
            let totalApproved = 0;
            let totalMuatan = 0;
            
            uniqueSlsMap.forEach(val => {
                totalOpen += val.OPEN;
                totalDraft += val.DRAFT;
                totalSubmitted += val.SUBMITTED;
                totalRejected += val.REJECTED;
                totalApproved += val.APPROVED;
                totalMuatan += val.muatan;
            });
            
            // Get values from official progresData if available, otherwise fallback to sums
            const valApproved = (typeof progresData !== 'undefined' && progresData && 'APPROVED BY Pengawas' in progresData) ? parseInt(progresData['APPROVED BY Pengawas']) : totalApproved;
            const valSubmitted = (typeof progresData !== 'undefined' && progresData && 'SUBMITTED BY Pencacah' in progresData) ? parseInt(progresData['SUBMITTED BY Pencacah']) : totalSubmitted;
            const valDraft = (typeof progresData !== 'undefined' && progresData && 'DRAFT' in progresData) ? parseInt(progresData['DRAFT']) : totalDraft;
            const valOpen = (typeof progresData !== 'undefined' && progresData && 'OPEN' in progresData) ? parseInt(progresData['OPEN']) : totalOpen;
            const valRejected = (typeof progresData !== 'undefined' && progresData && 'REJECTED BY Pengawas' in progresData) ? parseInt(progresData['REJECTED BY Pengawas']) : totalRejected;
            
            // Update fields
            document.getElementById('kpiTotalSLS').textContent = uniqueSlsMap.size.toLocaleString('id-ID');
            const scrapedTargetMuatan = (typeof assignData !== 'undefined' && assignData && assignData.assigned) ? parseInt(assignData.assigned) : totalMuatan;
            document.getElementById('kpiTotalMuatan').textContent = scrapedTargetMuatan.toLocaleString('id-ID');
            document.getElementById('kpiTotalWilkerstat').textContent = totalMuatan.toLocaleString('id-ID');
            document.getElementById('kpiOpen').textContent = valOpen.toLocaleString('id-ID');
            document.getElementById('kpiDraft').textContent = valDraft.toLocaleString('id-ID');
            document.getElementById('kpiSubmitted').textContent = valSubmitted.toLocaleString('id-ID');
            document.getElementById('kpiRejected').textContent = valRejected.toLocaleString('id-ID');
            document.getElementById('kpiApproved').textContent = valApproved.toLocaleString('id-ID');
            
            // Progress Calculation
            const completed = valApproved + valSubmitted + valRejected;
            const progressPct = scrapedTargetMuatan > 0 ? (completed / scrapedTargetMuatan) * 100 : 0;
            
            document.getElementById('kpiProgressPct').textContent = progressPct.toFixed(2) + '%';
            document.getElementById('kpiProgressRatio').textContent = `${completed.toLocaleString('id-ID')} / ${scrapedTargetMuatan.toLocaleString('id-ID')} Rincian Usaha`;
            document.getElementById('kpiProgressBar').style.width = progressPct.toFixed(2) + '%';
        }

        // Switch Tab
        function switchTab(tabName) {
            currentTab = tabName;
            
            // Update active state of buttons
            const buttons = document.querySelectorAll('.tab-btn');
            buttons.forEach(btn => {
                btn.classList.remove('active');
                if (btn.outerHTML.includes(`switchTab('${tabName}')`)) {
                    btn.classList.add('active');
                }
            });
            
            renderActiveTab();
        }

        // Apply filters to rawScrapedData
        function getFilteredData() {
            return rawScrapedData.filter(row => {
                // 1. Search Query
                if (searchQuery.trim() !== '') {
                    const q = searchQuery.toLowerCase();
                    const email = (row.Email || '').toLowerCase();
                    const slsCode = (row["SLS Code"] || '').toLowerCase();
                    const namaPetugas = (row.nama_petugas || '').toLowerCase();
                    const kecName = (row.nama_kec || '').toLowerCase();
                    const koseka = (row.koseka || '').toLowerCase();
                    
                    const match = email.includes(q) || 
                                  slsCode.includes(q) || 
                                  namaPetugas.includes(q) || 
                                  kecName.includes(q) || 
                                  koseka.includes(q);
                    
                    if (!match) return false;
                }
                
                // 2. Kecamatan
                if (filterKec !== '') {
                    const rowKec = row.nama_kec || row.kd_kec || '';
                    if (rowKec.trim() !== filterKec.trim()) return false;
                }
                
                // 3. Category/Role
                if (filterCategory !== '') {
                    if (getNormalizedRole(row) !== filterCategory) return false;
                }
                
                // 4. Priority SLS
                if (filterPriority !== '') {
                    if (row.is_prioritas !== filterPriority) return false;
                }
                
                return true;
            });
        }

        // Sorting Helper
        function sortDataset(array, field, isAscending) {
            return array.sort((a, b) => {
                let valA = a[field];
                let valB = b[field];
                
                // Handle parsing numbers
                if (!isNaN(valA) && !isNaN(valB)) {
                    valA = Number(valA);
                    valB = Number(valB);
                } else {
                    valA = (valA || '').toString().toLowerCase();
                    valB = (valB || '').toString().toLowerCase();
                }
                
                if (valA < valB) return isAscending ? -1 : 1;
                if (valA > valB) return isAscending ? 1 : -1;
                return 0;
            });
        }

        // Render Active Tab
        function renderActiveTab() {
            const container = document.getElementById('tabContentContainer');
            container.innerHTML = '';
            
            const filtered = getFilteredData();
            
            const tabDiv = document.createElement('div');
            tabDiv.className = 'animated-tab';
            
            if (currentTab === 'kecamatan') {
                renderKecamatanTab(tabDiv, filtered);
            } else if (currentTab === 'petugas') {
                renderPetugasTab(tabDiv, filtered);
            } else if (currentTab === 'detail') {
                renderDetailTab(tabDiv, filtered);
            }
            
            container.appendChild(tabDiv);
        }

        // Tab 1: Rekap Kecamatan
        function renderKecamatanTab(tabDiv, filteredData) {
            // Aggregate by Kecamatan, counting each SLS Code only once
            const kecMap = {};
            const processedSls = new Set();
            
            filteredData.forEach(row => {
                const slsCode = row["SLS Code"];
                if (slsCode) {
                    if (processedSls.has(slsCode)) return;
                    processedSls.add(slsCode);
                }
                
                let kecName = row.nama_kec || '';
                kecName = kecName.trim();
                if (!kecName || kecName === 'TIDAK TERIDENTIFIKASI') return;
                
                if (!kecMap[kecName]) {
                    kecMap[kecName] = {
                        nama_kec: kecName,
                        total_sls: 0,
                        muatan: 0,
                        OPEN: 0,
                        DRAFT: 0,
                        SUBMITTED: 0,
                        REJECTED: 0,
                        APPROVED: 0
                    };
                }
                
                const open = parseInt(row.OPEN) || 0;
                const draft = parseInt(row.DRAFT) || 0;
                const sub = parseInt(row["SUBMITTED BY Pencacah"]) || 0;
                const rej = parseInt(row["REJECTED BY Pengawas"]) || 0;
                const app = parseInt(row["APPROVED BY Pengawas"]) || 0;
                const muatan = parseInt(row.muatan_wilkerstat) || 0;
                
                kecMap[kecName].OPEN += open;
                kecMap[kecName].DRAFT += draft;
                kecMap[kecName].SUBMITTED += sub;
                kecMap[kecName].REJECTED += rej;
                kecMap[kecName].APPROVED += app;
                kecMap[kecName].total_sls += 1;
                kecMap[kecName].muatan += muatan;
            });
            
            const kecList = Object.values(kecMap);
            
            // Calculate progress rate and assign to list
            kecList.forEach(k => {
                const comp = k.APPROVED + k.SUBMITTED + k.REJECTED;
                k.progress_rate = k.muatan > 0 ? (comp / k.muatan) * 100 : 0;
            });
            
            // Sort
            sortDataset(kecList, sortKecField, sortKecAsc);
            
            if (kecList.length === 0) {
                renderEmptyState(tabDiv);
                return;
            }
            
            // Render Table HTML
            let html = `
                <div class="table-card">
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th class="no-sort" style="width: 50px;">No</th>
                                    <th onclick="handleKecSort('nama_kec')">Kecamatan ${getSortArrow('nama_kec', sortKecField, sortKecAsc)}</th>
                                    <th onclick="handleKecSort('total_sls')">Jumlah SLS ${getSortArrow('total_sls', sortKecField, sortKecAsc)}</th>
                                    <th onclick="handleKecSort('muatan')">Muatan Wilkerstat ${getSortArrow('muatan', sortKecField, sortKecAsc)}</th>
                                    <th onclick="handleKecSort('OPEN')">Open ${getSortArrow('OPEN', sortKecField, sortKecAsc)}</th>
                                    <th onclick="handleKecSort('DRAFT')">Draft ${getSortArrow('DRAFT', sortKecField, sortKecAsc)}</th>
                                    <th onclick="handleKecSort('SUBMITTED')">Submitted ${getSortArrow('SUBMITTED', sortKecField, sortKecAsc)}</th>
                                    <th onclick="handleKecSort('REJECTED')">Rejected ${getSortArrow('REJECTED', sortKecField, sortKecAsc)}</th>
                                    <th onclick="handleKecSort('APPROVED')">Approved ${getSortArrow('APPROVED', sortKecField, sortKecAsc)}</th>
                                    <th onclick="handleKecSort('progress_rate')">Progress Rate ${getSortArrow('progress_rate', sortKecField, sortKecAsc)}</th>
                                </tr>
                            </thead>
                            <tbody>
            `;
            
            kecList.forEach((kec, idx) => {
                html += `
                    <tr>
                        <td>${idx + 1}</td>
                        <td style="font-weight: 600; color: var(--primary)">${kec.nama_kec}</td>
                        <td style="font-weight: 500;">${kec.total_sls.toLocaleString('id-ID')}</td>
                        <td style="font-weight: 500; color: #475569;">${kec.muatan.toLocaleString('id-ID')}</td>
                        <td class="txt-open">${kec.OPEN.toLocaleString('id-ID')}</td>
                        <td class="txt-draft">${kec.DRAFT.toLocaleString('id-ID')}</td>
                        <td class="txt-submitted">${kec.SUBMITTED.toLocaleString('id-ID')}</td>
                        <td class="txt-rejected">${kec.REJECTED.toLocaleString('id-ID')}</td>
                        <td class="txt-approved">${kec.APPROVED.toLocaleString('id-ID')}</td>
                        <td>
                            <div class="progress-cell">
                                <div class="progress-bar-cell-bg">
                                    <div class="progress-bar-cell-fill" style="width: ${kec.progress_rate.toFixed(1)}%"></div>
                                </div>
                                <span class="progress-percent-text">${kec.progress_rate.toFixed(1)}%</span>
                            </div>
                        </td>
                    </tr>
                `;
            });
            
            html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
            
            tabDiv.innerHTML = html;
        }
        
        function handleKecSort(field) {
            if (sortKecField === field) {
                sortKecAsc = !sortKecAsc;
            } else {
                sortKecField = field;
                sortKecAsc = !numericFields.includes(field);
            }
            renderActiveTab();
        }

        // Tab 2: Rekap Petugas
        function renderPetugasTab(tabDiv, filteredData) {
            const petMap = {};
            filteredData.forEach(row => {
                const email = row.Email ? row.Email.trim().toLowerCase() : '';
                if (!email) return;
                
                let key = email;
                if (!petMap[key]) {
                    petMap[key] = {
                        email: email,
                        nama_petugas: row.nama_petugas || row.Email || 'Belum Ditentukan',
                        jabatan_petugas: getNormalizedRole(row),
                        total_sls: 0,
                        muatan: 0,
                        OPEN: 0,
                        DRAFT: 0,
                        SUBMITTED: 0,
                        REJECTED: 0,
                        APPROVED: 0
                    };
                }
                
                const open = parseInt(row.OPEN) || 0;
                const draft = parseInt(row.DRAFT) || 0;
                const sub = parseInt(row["SUBMITTED BY Pencacah"]) || 0;
                const rej = parseInt(row["REJECTED BY Pengawas"]) || 0;
                const app = parseInt(row["APPROVED BY Pengawas"]) || 0;
                const muatan = parseInt(row.muatan_wilkerstat) || 0;
                
                petMap[key].OPEN += open;
                petMap[key].DRAFT += draft;
                petMap[key].SUBMITTED += sub;
                petMap[key].REJECTED += rej;
                petMap[key].APPROVED += app;
                if (row["SLS Code"]) {
                    petMap[key].total_sls += 1;
                }
                petMap[key].muatan += muatan;
            });
            
            const petList = Object.values(petMap);
            
            petList.forEach(p => {
                const comp = p.APPROVED + p.SUBMITTED + p.REJECTED;
                p.progress_rate = p.muatan > 0 ? (comp / p.muatan) * 100 : 0;
            });
            
            sortDataset(petList, sortPetField, sortPetAsc);
            
            if (petList.length === 0) {
                renderEmptyState(tabDiv);
                return;
            }
            
            let html = `
                <div class="table-card">
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th class="no-sort" style="width: 50px;">No</th>
                                    <th onclick="handlePetSort('nama_petugas')">Nama Petugas ${getSortArrow('nama_petugas', sortPetField, sortPetAsc)}</th>
                                    <th onclick="handlePetSort('email')">Email ${getSortArrow('email', sortPetField, sortPetAsc)}</th>
                                    <th onclick="handlePetSort('jabatan_petugas')">Peran ${getSortArrow('jabatan_petugas', sortPetField, sortPetAsc)}</th>
                                    <th onclick="handlePetSort('total_sls')">Total SLS ${getSortArrow('total_sls', sortPetField, sortPetAsc)}</th>
                                    <th onclick="handlePetSort('muatan')">Muatan Wilkerstat ${getSortArrow('muatan', sortPetField, sortPetAsc)}</th>
                                    <th onclick="handlePetSort('OPEN')">Open ${getSortArrow('OPEN', sortPetField, sortPetAsc)}</th>
                                    <th onclick="handlePetSort('DRAFT')">Draft ${getSortArrow('DRAFT', sortPetField, sortPetAsc)}</th>
                                    <th onclick="handlePetSort('SUBMITTED')">Submitted ${getSortArrow('SUBMITTED', sortPetField, sortPetAsc)}</th>
                                    <th onclick="handlePetSort('REJECTED')">Rejected ${getSortArrow('REJECTED', sortPetField, sortPetAsc)}</th>
                                    <th onclick="handlePetSort('APPROVED')">Approved ${getSortArrow('APPROVED', sortPetField, sortPetAsc)}</th>
                                    <th onclick="handlePetSort('progress_rate')">Progress Rate ${getSortArrow('progress_rate', sortPetField, sortPetAsc)}</th>
                                </tr>
                            </thead>
                            <tbody>
            `;
            
            petList.forEach((pet, idx) => {
                html += `
                    <tr>
                        <td>${idx + 1}</td>
                        <td style="font-weight: 600; color: var(--primary)">${pet.nama_petugas}</td>
                        <td style="color: var(--text-muted)">${pet.email}</td>
                        <td><span class="badge badge-role">${pet.jabatan_petugas}</span></td>
                        <td style="font-weight: 500;">${pet.total_sls.toLocaleString('id-ID')}</td>
                        <td style="font-weight: 500; color: #475569;">${pet.muatan.toLocaleString('id-ID')}</td>
                        <td class="txt-open">${pet.OPEN.toLocaleString('id-ID')}</td>
                        <td class="txt-draft">${pet.DRAFT.toLocaleString('id-ID')}</td>
                        <td class="txt-submitted">${pet.SUBMITTED.toLocaleString('id-ID')}</td>
                        <td class="txt-rejected">${pet.REJECTED.toLocaleString('id-ID')}</td>
                        <td class="txt-approved">${pet.APPROVED.toLocaleString('id-ID')}</td>
                        <td>
                            <div class="progress-cell">
                                <div class="progress-bar-cell-bg">
                                    <div class="progress-bar-cell-fill" style="width: ${pet.progress_rate.toFixed(1)}%"></div>
                                </div>
                                <span class="progress-percent-text">${pet.progress_rate.toFixed(1)}%</span>
                            </div>
                        </td>
                    </tr>
                `;
            });
            
            html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
            
            tabDiv.innerHTML = html;
        }
        
        function handlePetSort(field) {
            if (sortPetField === field) {
                sortPetAsc = !sortPetAsc;
            } else {
                sortPetField = field;
                sortPetAsc = !numericFields.includes(field);
            }
            renderActiveTab();
        }

        // Tab 3: Detail SLS (with pagination)
        function renderDetailTab(tabDiv, filteredData) {
            // De-duplicate by SLS Code to show only one row per SLS
            const uniqueDetailMap = new Map();
            filteredData.forEach(row => {
                const slsCode = row["SLS Code"];
                if (!slsCode) {
                    const key = "blank_" + row.Email;
                    uniqueDetailMap.set(key, row);
                    return;
                }
                if (!uniqueDetailMap.has(slsCode)) {
                    uniqueDetailMap.set(slsCode, { ...row });
                } else {
                    const existing = uniqueDetailMap.get(slsCode);
                    const existingRole = getNormalizedRole(existing);
                    const currentRole = getNormalizedRole(row);
                    if (existingRole === 'PML' && currentRole === 'PPL') {
                        existing.Email = row.Email;
                        existing.Category = row.Category;
                        existing.nama_petugas = row.nama_petugas;
                        existing.jabatan_petugas = row.jabatan_petugas;
                    }
                }
            });
            const dedupedData = Array.from(uniqueDetailMap.values());

            // Calculate progress rate for each SLS before sorting
            dedupedData.forEach(row => {
                const sub = parseInt(row["SUBMITTED BY Pencacah"]) || 0;
                const rej = parseInt(row["REJECTED BY Pengawas"]) || 0;
                const app = parseInt(row["APPROVED BY Pengawas"]) || 0;
                const muatan = parseInt(row.muatan_wilkerstat) || 0;
                const comp = app + sub + rej;
                row.progress_rate = muatan > 0 ? (comp / muatan) * 100 : 0;
            });

            // Sort
            sortDataset(dedupedData, sortDetField, sortDetAsc);
            
            // Pagination math
            const totalItems = dedupedData.length;
            const totalPages = Math.ceil(totalItems / detailItemsPerPage);
            
            if (detailCurrentPage > totalPages) {
                detailCurrentPage = Math.max(1, totalPages);
            }
            
            const startIndex = (detailCurrentPage - 1) * detailItemsPerPage;
            const endIndex = Math.min(startIndex + detailItemsPerPage, totalItems);
            const paginatedData = dedupedData.slice(startIndex, endIndex);
            
            if (totalItems === 0) {
                renderEmptyState(tabDiv);
                return;
            }
            
            let html = `
                <div class="table-card">
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th class="no-sort" style="width: 50px;">No</th>
                                    <th onclick="handleDetSort('SLS Code')">Kode SLS ${getSortArrow('SLS Code', sortDetField, sortDetAsc)}</th>
                                    <th onclick="handleDetSort('nama_petugas')">Nama Petugas ${getSortArrow('nama_petugas', sortDetField, sortDetAsc)}</th>
                                    <th onclick="handleDetSort('Category')">Peran ${getSortArrow('Category', sortDetField, sortDetAsc)}</th>
                                    <th onclick="handleDetSort('nama_kec')">Kecamatan ${getSortArrow('nama_kec', sortDetField, sortDetAsc)}</th>
                                    <th onclick="handleDetSort('is_prioritas')">Prioritas ${getSortArrow('is_prioritas', sortDetField, sortDetAsc)}</th>
                                    <th onclick="handleDetSort('muatan_wilkerstat')">Muatan ${getSortArrow('muatan_wilkerstat', sortDetField, sortDetAsc)}</th>
                                    <th onclick="handleDetSort('OPEN')">Open ${getSortArrow('OPEN', sortDetField, sortDetAsc)}</th>
                                    <th onclick="handleDetSort('DRAFT')">Draft ${getSortArrow('DRAFT', sortDetField, sortDetAsc)}</th>
                                    <th onclick="handleDetSort('SUBMITTED BY Pencacah')">Submitted ${getSortArrow('SUBMITTED BY Pencacah', sortDetField, sortDetAsc)}</th>
                                    <th onclick="handleDetSort('REJECTED BY Pengawas')">Rejected ${getSortArrow('REJECTED BY Pengawas', sortDetField, sortDetAsc)}</th>
                                    <th onclick="handleDetSort('APPROVED BY Pengawas')">Approved ${getSortArrow('APPROVED BY Pengawas', sortDetField, sortDetAsc)}</th>
                                    <th onclick="handleDetSort('progress_rate')">Progress Rate ${getSortArrow('progress_rate', sortDetField, sortDetAsc)}</th>
                                </tr>
                            </thead>
                            <tbody>
            `;
            
            paginatedData.forEach((row, idx) => {
                const priorBadge = row.is_prioritas === 'Ya' 
                    ? '<span class="badge badge-priority">Prioritas</span>' 
                    : '<span class="badge badge-non-priority">Biasa</span>';
                
                html += `
                    <tr>
                        <td>${startIndex + idx + 1}</td>
                        <td style="font-family: monospace; font-weight: 600; color: #334155">${row["SLS Code"]}</td>
                        <td style="font-weight: 500; color: var(--primary)">${row.nama_petugas || '-'}</td>
                        <td><span class="badge badge-role">${getNormalizedRole(row)}</span></td>
                        <td>${row.nama_kec || '-'}</td>
                        <td>${priorBadge}</td>
                        <td>${row.muatan_wilkerstat}</td>
                        <td class="txt-open">${row.OPEN}</td>
                        <td class="txt-draft">${row.DRAFT}</td>
                        <td class="txt-submitted">${row["SUBMITTED BY Pencacah"]}</td>
                        <td class="txt-rejected">${row["REJECTED BY Pengawas"]}</td>
                        <td class="txt-approved">${row["APPROVED BY Pengawas"]}</td>
                        <td>
                            <div class="progress-cell">
                                <div class="progress-bar-cell-bg">
                                    <div class="progress-bar-cell-fill" style="width: ${row.progress_rate.toFixed(1)}%"></div>
                                </div>
                                <span class="progress-percent-text">${row.progress_rate.toFixed(1)}%</span>
                            </div>
                        </td>
                    </tr>
                `;
            });
            
            html += `
                            </tbody>
                        </table>
                    </div>
                    
                    <!-- Pagination Footer -->
                    <div class="pagination-footer">
                        <div class="pagination-info">
                            Menampilkan <strong>${startIndex + 1}</strong> - <strong>${endIndex}</strong> dari <strong>${totalItems}</strong> SLS
                        </div>
                        
                        <div class="pagination-controls">
                            <button class="page-btn" onclick="handlePageChange(1)" ${detailCurrentPage === 1 ? 'disabled' : ''}>&laquo;</button>
                            <button class="page-btn" onclick="handlePageChange(${detailCurrentPage - 1})" ${detailCurrentPage === 1 ? 'disabled' : ''}>&lsaquo;</button>
                            
                            <span style="font-size: 0.8125rem; margin: 0 0.5rem;">Halaman <strong>${detailCurrentPage}</strong> dari <strong>${totalPages}</strong></span>
                            
                            <button class="page-btn" onclick="handlePageChange(${detailCurrentPage + 1})" ${detailCurrentPage === totalPages ? 'disabled' : ''}>&rsaquo;</button>
                            <button class="page-btn" onclick="handlePageChange(${totalPages})" ${detailCurrentPage === totalPages ? 'disabled' : ''}>&raquo;</button>
                        </div>
                    </div>
                </div>
            `;
            
            tabDiv.innerHTML = html;
        }

        function handleDetSort(field) {
            if (sortDetField === field) {
                sortDetAsc = !sortDetAsc;
            } else {
                sortDetField = field;
                sortDetAsc = !numericFields.includes(field);
            }
            detailCurrentPage = 1;
            renderActiveTab();
        }

        function handlePageChange(newPage) {
            detailCurrentPage = newPage;
            renderActiveTab();
        }

        // Get sort arrow visual indicators
        function getSortArrow(field, currentSortField, isAsc) {
            if (field !== currentSortField) {
                return '<span class="sort-indicator" style="opacity: 0.35;">⇅</span>';
            }
            return isAsc ? '<span class="sort-indicator">▲</span>' : '<span class="sort-indicator">▼</span>';
        }

        // Empty state HTML renderer
        function renderEmptyState(tabDiv) {
            tabDiv.innerHTML = `
                <div class="table-card">
                    <div class="empty-state">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="11" cy="11" r="8"/>
                            <path d="m21 21-4.3-4.3"/>
                        </svg>
                        <h3>Tidak ada data ditemukan</h3>
                        <p style="margin-top: 0.5rem; font-size: 0.875rem;">Silakan ubah query pencarian atau reset filter Anda.</p>
                    </div>
                </div>
            `;
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    process_data()

