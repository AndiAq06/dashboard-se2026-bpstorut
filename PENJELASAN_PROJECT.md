# Penjelasan Project: Sistem Monitoring FASIH Sensus Ekonomi 2026
**BPS Kabupaten Kepulauan Sangihe**

---

## Gambaran Umum

Project ini adalah **sistem pemantauan otomatis** untuk mendukung pelaksanaan **Sensus Ekonomi 2026 (SE2026)** di Kabupaten Kepulauan Sangihe. Sistem ini memiliki dua fungsi utama: mengumpulkan data progres kerja petugas lapangan secara otomatis dari portal BPS FASIH, dan menampilkannya dalam bentuk dashboard visual yang mudah dipahami.

Tanpa sistem ini, pemantauan progres harus dilakukan secara manual — membuka portal FASIH satu per satu untuk setiap petugas. Dengan sistem ini, seluruh data dikumpulkan otomatis dan langsung tersaji dalam satu halaman dashboard.

---

## Masalah yang Diselesaikan

Portal BPS FASIH (Flexible Authentic Survey Instrument in Harmony) menyimpan data prelist setiap petugas pencacah (PPL) secara individual. Untuk memantau progres 168+ petugas, seseorang harus mencari satu per satu secara manual. Project ini mengotomatiskan proses tersebut sehingga:

- Data seluruh petugas dapat dikumpulkan dalam sekali jalan
- Status terbaru (Open, Draft, Submit, Approve, Reject) langsung terpantau
- Pimpinan/koordinator dapat melihat siapa yang sudah/belum mengerjakan tugas tanpa masuk ke portal

---

## Arsitektur Sistem

Sistem ini terdiri dari **dua komponen utama** yang bekerja secara berurutan:

```
[Portal BPS FASIH]
        │
        ▼
[1. Scraper Python (Playwright)]
   - Login otomatis ke FASIH
   - Iterasi 168 email petugas
   - Kumpulkan data prelist per petugas
   - Simpan ke scraped_data.csv
        │
        ▼
[2. Prosesor Data (process_data.py)]
   - Petakan kode SLS → Kecamatan
   - Relasikan PPL ke PML
   - Hasilkan update_data.csv
   - Push otomatis ke GitHub
        │
        ▼
[3. Dashboard Next.js (Vercel)]
   - Baca update_data.csv dari /public
   - Tampilkan statistik, tabel, leaderboard
   - Akses via browser kapan saja
```

---

## Komponen 1: Scraper Python

**File utama:** `run_scraper.py`

Scraper menggunakan **Playwright** (library otomasi browser) untuk:
1. Membuka browser secara otomatis (Chromium)
2. Login ke portal FASIH menggunakan sesi tersimpan (`auth_state.json`)
3. Mencari satu per satu email petugas dari daftar `email_mitra.txt` (168 email)
4. Mengambil semua data prelist yang muncul untuk setiap petugas
5. Menyimpan hasilnya ke `scraped_data.csv`

**Mode Menjalankan:**
- `python run_scraper.py --test` → hanya 3 email (untuk uji coba)
- `python run_scraper.py` → semua 168 email (produksi penuh)

**Data yang dikumpulkan per baris prelist:**

| Kolom | Contoh |
|---|---|
| Searched Email | adityahangau@gmail.com |
| Kode Identitas | 7103090014000100 - DTSEN - 45 |
| Nama Keluarga/Usaha | DANIEL NANGKODA |
| Skala Usaha / Jenis Prelist | KELUARGA / UMK / UMB |
| Status | open / draft / submit / approve / reject |
| Petugas Saat Ini | adityahangau@gmail.comPencacah |

Saat ini database berisi **±47.370 baris data** hasil scraping.

---

## Komponen 2: Pemrosesan Data

**File utama:** `process_data.py`

Setelah scraping selesai, data mentah diolah untuk:

**a. Pemetaan Kecamatan**
Kode identitas prelist (contoh: `7103090014000100`) mengandung 7 digit kode wilayah (`7103090`). Kode ini dicocokkan dengan file `koseka.csv` untuk mendapatkan nama kecamatan dan nama Koseka (Koordinator Sensus Kecamatan).

**b. Relasi PML ↔ PPL**
File `pml_ppl.csv` berisi daftar PML (Pengawas Lapangan) dan PPL/PCL (Pencacah). Karena tidak ada relasi langsung, pemetaan dilakukan berdasarkan kesamaan kecamatan — PPL yang bertugas di kecamatan yang sama dengan PML otomatis terhubung.

**c. Klasifikasi Status**
Status prelist diklasifikasikan sebagai berikut:

| Status | Keterangan |
|---|---|
| **Open** | Belum dikerjakan sama sekali |
| **Draft** | Sudah dibuka/dikerjakan sebagian |
| **Submit** | Sudah diselesaikan dan dikirim petugas |
| **Approve** | Sudah disetujui oleh pengawas (PML) |
| **Reject** | Dikembalikan untuk diperbaiki |

**Realisasi** dihitung dari jumlah prelist dengan status Submit + Approve + Reject.

**d. Auto Git Push**
Setelah data diproses dan disalin ke folder `dashboard/public/`, skrip otomatis melakukan `git commit` dan `git push` sehingga Vercel (hosting dashboard) langsung memperbarui tampilannya.

---

## Komponen 3: Dashboard Monitoring (Next.js)

**Folder:** `dashboard/`  
**Akses:** `http://localhost:3000` (lokal) atau via Vercel (online)

Dashboard dibangun dengan **Next.js + Tailwind CSS** dengan tema warna oranye (identitas BPS). Terdiri dari dua halaman:

### Halaman Utama (`/`)
- **Statistik ringkasan:** Total prelist, total realisasi, persentase progres keseluruhan
- **Tabel pencarian:** Cari petugas berdasarkan nama/email, lihat status prelist masing-masing
- **Leaderboard:** Peringkat petugas berdasarkan capaian progres
- **Grafik distribusi:** Sebaran jenis prelist (KELUARGA, UMK, UMB) per petugas

### Halaman Tabulasi (`/tabulasi`)
- **Tabel Detail PCL:** Rincian progres per petugas pencacah (Open/Draft/Submit/Approve/Reject)
- **Tabel Ringkasan Kecamatan:** Rekapitulasi progres per kecamatan

---

## Struktur File Kunci

```
scraper-fasih-sm/
├── run_scraper.py          # Scraper utama (Playwright)
├── process_data.py         # Pemrosesan & pipeline data
├── scraped_data.csv        # Data mentah hasil scraping (±47.370 baris)
├── auth_state.json         # Sesi login FASIH (RAHASIA, tidak di-push)
├── data/
│   ├── email_mitra.txt     # 168 email petugas pencacah
│   ├── koseka.csv          # Pemetaan kode kecamatan
│   └── pml_ppl.csv         # Daftar PML dan PPL beserta wilayah
└── dashboard/
    ├── public/
    │   ├── update_data.csv     # Data olahan untuk dashboard
    │   ├── pml_ppl.csv         # Data relasi petugas
    │   └── last_updated.txt    # Timestamp pembaruan terakhir
    └── src/app/
        ├── page.tsx            # Halaman utama dashboard
        └── tabulasi/page.tsx   # Halaman tabulasi kecamatan
```

---

## Alur Kerja Harian

```
1. Buka terminal di folder root project
2. Jalankan: python run_scraper.py
   ↳ Browser otomatis buka & scrape data FASIH (~168 petugas)
   ↳ Data diproses & disalin ke dashboard/public/
   ↳ Git push otomatis → Vercel refresh dashboard
3. Buka dashboard (localhost:3000 atau URL Vercel)
   ↳ Pantau progres seluruh petugas secara real-time
```

---

## Deployment

Dashboard dapat dihosting secara gratis di **Vercel** dengan cara:
1. Push repositori ke GitHub
2. Hubungkan repo ke Vercel
3. Set **Root Directory** ke folder `dashboard`
4. Deploy — Vercel otomatis mendeteksi Next.js

Setiap kali `process_data.py` dijalankan dan melakukan git push, Vercel akan otomatis men-deploy ulang dengan data terbaru.

---

## Keamanan

- File `auth_state.json` (berisi sesi login FASIH) **tidak boleh** diunggah ke GitHub — sudah dikecualikan via `.gitignore`
- Daftar email petugas disimpan lokal dan tidak dipublikasikan
- Akses dashboard bersifat publik (read-only) — tidak ada data sensitif yang ditampilkan

---

*Dokumentasi ini dibuat untuk keperluan pemahaman dan pengembangan sistem monitoring SE2026 BPS Kabupaten Kepulauan Sangihe.*
