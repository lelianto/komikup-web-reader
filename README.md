# KomikRoll

Web reader komik + scraper. Konten bersumber dari [komikup.com](https://www.komikup.com/).

## Scraper & Downloader (`scraper.py`)

Script Python untuk mengambil (scrape) konten dari **[komikup.com](https://www.komikup.com/)**:
1. **Daftar Komik & Metadata**: Update terbaru, direktori per tipe (`manga`, `manhwa`, `manhua`), filter abjad (`A-Z`), pencarian, serta daftar komik terpopuler (`daily`, `weekly`, `monthly`).
2. **Detail Komik & Daftar Chapter**: Judul, judul alternatif (Indonesia), tipe, author, tema, status, genre, sinopsis, cover URL, dan seluruh daftar chapter beserta link-nya.
3. **Gambar Halaman per Chapter (Unduh Komik)**: Mengambil seluruh URL gambar per halaman (otomatis melewati pengunci layar / iklan *Buka Akses Membaca* di web), mengunduhnya secara paralel (multi-threading), serta opsi membungkus menjadi file `.cbz`.

> **Tanpa Dependency Tambahan**: Script ini menggunakan *Python Standard Library* bawaan Python 3, sehingga bisa langsung dijalankan tanpa perlu `pip install`.

---

## Cara Penggunaan

Pastikan berada di direktori project:
```bash
cd /Users/lelianto/Documents/Works/manga
```

### 1. Scrape Daftar Komik Terbaru (`newest`)
Mengambil daftar komik update terbaru (bisa disimpan ke `.json` atau `.csv`):
```bash
# Tampilkan ke layar (halaman 1)
python3 scraper.py newest

# Ambil 3 halaman pertama dan simpan ke file JSON / CSV
python3 scraper.py newest -p 3 -o data/newest.json
python3 scraper.py newest -p 3 -o data/newest.csv
```

### 2. Scrape Direktori Komik per Tipe & Abjad (`list`)
Mengambil daftar komik berdasarkan tipe (`manga`, `manhwa`, `manhua`) dan opsional filter huruf (`A-Z`):
```bash
# Ambil daftar Manhwa halaman 1-2
python3 scraper.py list -t manhwa -p 2 -o data/manhwa.json

# Ambil daftar Manga berawalan huruf 'A' sekaligus ambil metadata detail & semua chapter-nya
python3 scraper.py list -t manga -l A -p 1 --with-details -o data/manga_A_full.json
```

### 3. Cari Komik (`search`)
```bash
# Cari komik berdasarkan kata kunci
python3 scraper.py search "regression" -o data/search_regression.json

# Cari sekaligus ambil detail lengkap & daftar chapter tiap hasil
python3 scraper.py search "regression" --with-details -o data/search_regression_full.json
```

### 4. Scrape Komik Terpopuler (`top`)
Mengambil daftar komik populer harian (`daily`), mingguan (`weekly`), dan bulanan (`monthly`):
```bash
python3 scraper.py top -o data/top_comics.json
```

### 5. Scrape Detail Komik & Seluruh Daftar Chapter (`detail`)
Bisa menggunakan URL lengkap dari `komikup.com` atau cukup slug/endpoint komiknya:
```bash
# Menggunakan slug atau endpoint
python3 scraper.py detail "1st-in-class-hides-regression" -o data/detail.json

# Atau menggunakan URL penuh dari browser
python3 scraper.py detail "https://www.komikup.com/?page=detail&ep=/manga/1st-in-class-hides-regression/" -o data/detail.json
```

### 6. Scrape / Unduh 1 Chapter Tertentu (`chapter`)
```bash
# Hanya ambil daftar URL gambar halaman (JSON)
python3 scraper.py chapter "/1st-in-class-hides-regression-chapter-1/" -o data/ch1_images.json

# Unduh semua gambar halaman chapter tersebut ke folder ./downloads
python3 scraper.py chapter "/1st-in-class-hides-regression-chapter-1/" -d downloads

# Unduh sekaligus buat file komik .cbz
python3 scraper.py chapter "/1st-in-class-hides-regression-chapter-1/" -d downloads --cbz
```

### 7. Unduh Komik Lengkap Beserta Chapter (`download`)
Perintah `download` akan otomatis membuat folder sesuai judul komik, menyimpan `comic_info.json`, mengunduh `cover.jpg`, dan mengunduh gambar halaman untuk chapter yang dipilih:
```bash
# Unduh 2 chapter mulai dari Chapter 1 (--from-start -n 2)
python3 scraper.py download "1st-in-class-hides-regression" --from-start -n 2 -d downloads

# Unduh rentang chapter tertentu (misal Chapter 1 sampai 5) dan bungkus jadi .cbz
python3 scraper.py download "1st-in-class-hides-regression" -c "1-5" --from-start --cbz -d downloads

# Unduh chapter tertentu saja (misal Chapter 1, 3, dan 10) dengan 8 worker paralel
python3 scraper.py download "1st-in-class-hides-regression" -c "1,3,10" -w 8 -d downloads

# Unduh SEMUA chapter dari suatu komik
python3 scraper.py download "1st-in-class-hides-regression" -d downloads
```

---

## Struktur Output Unduhan (`download`)
```text
downloads/
└── 1st in Class Hides Regression/
    ├── comic_info.json          # Metadata lengkap komik & daftar seluruh chapter
    ├── cover.webp               # Gambar sampul komik
    ├── 1st in Class Hides Regression Chapter 1/
    │   ├── chapter_info.json    # Metadata chapter & daftar URL gambar
    │   ├── 001.jpg              # Halaman 1
    │   ├── 002.jpg              # Halaman 2
    │   └── ...
    └── 1st in Class Hides Regression Chapter 1.cbz  # (Jika menggunakan flag --cbz)
```
