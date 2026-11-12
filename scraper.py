#!/usr/bin/env python3
"""
KomikUp (https://www.komikup.com/) Full Scraper & Downloader
Mengambil daftar komik, metadata detail, daftar chapter, hingga mengunduh gambar halaman per chapter.
Menggunakan Python Standard Library (tanpa perlu install library tambahan).
"""

import argparse
import concurrent.futures
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PRIMARY_API = "https://api.komikup.com/api"
FALLBACK_API = "https://api2.komikup.com/api"
SITE_URL = "https://www.komikup.com"
IMAGE_PROXY = "https://serveproxy.com/?url="

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": SITE_URL,
    "Referer": f"{SITE_URL}/",
}


def clean_endpoint(url_or_ep: str) -> str:
    """Normalisasi URL penuh atau parameter ?ep= menjadi path endpoint API yang bersih."""
    if not url_or_ep:
        return ""
    val = url_or_ep.strip()
    if val.startswith("http://") or val.startswith("https://"):
        parsed = urllib.parse.urlparse(val)
        qs = urllib.parse.parse_qs(parsed.query)
        if "ep" in qs and qs["ep"]:
            val = qs["ep"][0]
        else:
            val = parsed.path
    elif "ep=" in val:
        qs = urllib.parse.parse_qs(val.lstrip("?"))
        if "ep" in qs and qs["ep"]:
            val = qs["ep"][0]

    if not val.startswith("/"):
        val = "/" + val
    if not val.endswith("/"):
        val = val + "/"
    return val


def clean_comic_endpoint(comic_input: str) -> str:
    """Pastikan input slug/URL komik memiliki prefix /manga/<slug>/."""
    ep = clean_endpoint(comic_input)
    if not ep.startswith("/manga/"):
        slug = ep.strip("/")
        ep = f"/manga/{slug}/"
    return ep


def clean_chapter_endpoint(chapter_input: str) -> str:
    """Normalisasi input URL/slug chapter."""
    return clean_endpoint(chapter_input)


def sanitize_filename(name: str) -> str:
    """Bersihkan string agar aman dijadikan nama file/folder."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "untitled"


class KomikUpScraper:
    def __init__(self, timeout: int = 20, retries: int = 3, delay: float = 0.3):
        self.timeout = timeout
        self.retries = retries
        self.delay = delay

    def _request_json(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON dari PRIMARY_API dengan fallback otomatis ke FALLBACK_API."""
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        apis = [PRIMARY_API, FALLBACK_API]
        last_err = None

        for api_base in apis:
            url = f"{api_base}{endpoint}"
            for attempt in range(1, self.retries + 1):
                try:
                    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        raw = resp.read().decode("utf-8", errors="replace")
                        return json.loads(raw)
                except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
                    last_err = e
                    if attempt < self.retries:
                        time.sleep(self.delay * attempt)
            # Jika gagal di PRIMARY_API, lanjut ke FALLBACK_API

        print(f"[!] Gagal mengambil endpoint {endpoint}: {last_err}", file=sys.stderr)
        return None

    def _format_comic_card(self, item: Dict[str, Any], default_type: str = "") -> Dict[str, Any]:
        """Normalisasi item komik dari daftar/pencarian."""
        ep = clean_endpoint(item.get("endpoint") or item.get("slug") or "")
        if ep and not ep.startswith("/manga/"):
            ep = f"/manga/{ep.strip('/')}/"

        raw_img = item.get("image") or item.get("cover") or item.get("thumbnail") or ""
        chapters = []
        for ch in item.get("chapters") or []:
            ch_ep = clean_endpoint(ch.get("endpoint") or "")
            chapters.append({
                "title": ch.get("title") or ch.get("name") or "",
                "endpoint": ch_ep,
                "url": f"{SITE_URL}/?page=read&ep={ch_ep}" if ch_ep else "",
            })

        return {
            "title": item.get("title") or "",
            "type": item.get("type") or default_type or "Manga",
            "endpoint": ep,
            "detail_url": f"{SITE_URL}/?page=detail&ep={ep}" if ep else "",
            "cover_url": raw_img,
            "proxied_cover_url": f"{IMAGE_PROXY}{raw_img}" if raw_img and not raw_img.startswith(IMAGE_PROXY) else raw_img,
            "latest_chapters": chapters,
        }

    def get_newest(self, page: int = 1) -> List[Dict[str, Any]]:
        """Ambil daftar komik update terbaru per halaman."""
        res = self._request_json(f"/comic/newest/page/{page}")
        if not res or not res.get("data"):
            return []
        return [self._format_comic_card(item) for item in res["data"]]

    def get_comic_list(
        self, comic_type: str = "manga", page: int = 1, letter: str = ""
    ) -> List[Dict[str, Any]]:
        """Ambil daftar direktori komik berdasarkan tipe (manga/manhwa/manhua) & abjad."""
        params = {"filter": comic_type.lower(), "page": str(page)}
        if letter:
            params["huruf"] = letter.upper()
        query_string = urllib.parse.urlencode(params)
        res = self._request_json(f"/comic/list?{query_string}")
        if not res or not res.get("data"):
            return []
        return [self._format_comic_card(item, default_type=comic_type.capitalize()) for item in res["data"]]

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Cari komik berdasarkan kata kunci."""
        encoded_q = urllib.parse.quote(query.strip())
        res = self._request_json(f"/comic/search/{encoded_q}")
        if not res or not res.get("data"):
            return []
        return [self._format_comic_card(item) for item in res["data"]]

    def get_top_comics(self) -> Dict[str, List[Dict[str, Any]]]:
        """Ambil komik terpopuler (daily, weekly, monthly)."""
        res = self._request_json("/comic/top")
        if not res or res.get("status") != "success":
            return {}
        result: Dict[str, List[Dict[str, Any]]] = {}
        for period in ("daily", "weekly", "monthly"):
            items = res.get(period) or []
            result[period] = [self._format_comic_card(item) for item in items]
        return result

    def get_comic_detail(self, comic_input: str, known_type: str = "") -> Optional[Dict[str, Any]]:
        """Ambil metadata lengkap komik beserta seluruh daftar chapter."""
        ep = clean_comic_endpoint(comic_input)
        res = self._request_json(f"/comic/info{ep}")
        if not res or not res.get("data"):
            return None

        info = res["data"]
        raw_chapters = info.get("chapter_list") or info.get("chapters") or []
        chapters = []
        for ch in raw_chapters:
            ch_ep = clean_endpoint(ch.get("endpoint") or ch.get("slug") or "")
            chapters.append({
                "title": ch.get("name") or ch.get("title") or "",
                "date": ch.get("date") or ch.get("time") or "",
                "endpoint": ch_ep,
                "url": f"{SITE_URL}/?page=read&ep={ch_ep}" if ch_ep else "",
            })

        raw_genres = info.get("genre") or []
        if isinstance(raw_genres, str):
            genres = [g.strip() for g in raw_genres.split(",") if g.strip()]
        elif isinstance(raw_genres, list):
            genres = [str(g).strip() for g in raw_genres if str(g).strip()]
        else:
            genres = []

        thumb = info.get("thumbnail") or info.get("image") or ""

        # Normalisasi cerdas karena API KomikUp sering menggeser field tabel komiku:
        # - info['type'] sering berisi Judul Indonesia (kecuali bernilai Manga/Manhwa/Manhua)
        # - info['rating'] sering berisi Status ('Ongoing'/'Completed') atau Nama Author
        raw_type = (info.get("type") or "").strip()
        raw_rating = (info.get("rating") or info.get("score") or "").strip()
        raw_status = (info.get("status") or "").strip()
        raw_author = (info.get("author") or "").strip()

        valid_types = {"manga", "manhwa", "manhua"}
        if known_type:
            comic_type = known_type
            alt_title = raw_type if raw_type.lower() not in valid_types else ""
        elif raw_type.lower() in valid_types:
            comic_type = raw_type.capitalize()
            alt_title = info.get("alternative_title") or ""
        else:
            alt_title = raw_type
            # Coba deteksi tipe dari nama file thumbnail jika ada (misal: manga_thumbnail-Manhua-...)
            thumb_filename = thumb.rsplit("/", 1)[-1]
            m_type = re.search(r"[-_](Manga|Manhwa|Manhua)[-_.]", thumb_filename, re.IGNORECASE)
            comic_type = m_type.group(1).capitalize() if m_type else "Manga"

        if raw_rating.lower() in ("ongoing", "completed", "hiatus", "end", "tamat"):
            status = raw_rating
            author = raw_author or "Unknown"
            rating = ""
        else:
            status = raw_status if "\n" not in raw_status else "Ongoing"
            author = raw_rating if (raw_rating and not re.match(r"^\d+(\.\d+)?$", raw_rating)) else (raw_author or "Unknown")
            rating = raw_rating if re.match(r"^\d+(\.\d+)?$", raw_rating) else ""

        return {
            "title": info.get("title") or "",
            "alternative_title": alt_title,
            "type": comic_type,
            "author": author,
            "theme": raw_author,
            "status": status,
            "rating": rating,
            "genres": genres,
            "synopsis": info.get("description") or info.get("synopsis") or "",
            "cover_url": thumb,
            "proxied_cover_url": f"{IMAGE_PROXY}{thumb}" if thumb and not thumb.startswith(IMAGE_PROXY) else thumb,
            "endpoint": ep,
            "detail_url": f"{SITE_URL}/?page=detail&ep={ep}",
            "total_chapters": len(chapters),
            "raw_api_meta": {
                "type": raw_type,
                "author": raw_author,
                "status": raw_status,
                "rating": raw_rating,
            },
            "chapters": chapters,
        }

    def get_chapter_images(self, chapter_input: str) -> Optional[Dict[str, Any]]:
        """Ambil daftar gambar halaman dari satu chapter (dengan dukungan fallback /baca/)."""
        clean_ep = clean_chapter_endpoint(chapter_input)
        res = self._request_json(f"/comic/chapter{clean_ep}")

        # Fallback rute dengan atau tanpa /baca/ sesuai logika frontend KomikUp
        if not res or not res.get("data") or not res["data"].get("image"):
            if clean_ep.startswith("/baca/"):
                fallback_ep = clean_ep[len("/baca"):]
            else:
                fallback_ep = "/baca" + clean_ep
            res_fb = self._request_json(f"/comic/chapter{fallback_ep}")
            if res_fb and res_fb.get("data"):
                res = res_fb

        if not res or not res.get("data"):
            return None

        chap = res["data"]
        raw_images = chap.get("image") or []
        images = []
        for idx, img in enumerate(raw_images, start=1):
            raw_url = img if isinstance(img, str) else (img.get("url") or img.get("image") or "")
            if not raw_url:
                continue
            direct_url = raw_url
            if raw_url.startswith(IMAGE_PROXY):
                direct_url = raw_url[len(IMAGE_PROXY):]
            proxied_url = raw_url if raw_url.startswith(IMAGE_PROXY) else f"{IMAGE_PROXY}{raw_url}"
            images.append({
                "page": idx,
                "direct_url": direct_url,
                "proxied_url": proxied_url,
            })

        return {
            "title": chap.get("title") or clean_ep.strip("/"),
            "endpoint": clean_ep,
            "url": f"{SITE_URL}/?page=read&ep={clean_ep}",
            "total_pages": len(images),
            "images": images,
        }

    def _download_single_image(
        self, img_info: Dict[str, Any], dest_dir: Path, use_proxy: bool = False
    ) -> Tuple[int, Optional[Path], Optional[str]]:
        """Unduh satu gambar halaman dengan fallback otomatis antara direct URL dan proxy URL."""
        page_num = img_info["page"]
        urls_to_try = (
            [img_info["proxied_url"], img_info["direct_url"]]
            if use_proxy
            else [img_info["direct_url"], img_info["proxied_url"]]
        )

        # Tentukan ekstensi gambar
        parsed_path = urllib.parse.urlparse(img_info["direct_url"]).path
        ext = os.path.splitext(parsed_path)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            ext = ".jpg"

        out_path = dest_dir / f"{page_num:03d}{ext}"
        if out_path.exists() and out_path.stat().st_size > 0:
            return page_num, out_path, None

        last_err = None
        for url in urls_to_try:
            for attempt in range(1, self.retries + 1):
                try:
                    headers = dict(DEFAULT_HEADERS)
                    headers["Accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        data = resp.read()
                        if not data:
                            raise ValueError("Empty image response")
                        out_path.write_bytes(data)
                        return page_num, out_path, None
                except Exception as e:
                    last_err = str(e)
                    if attempt < self.retries:
                        time.sleep(self.delay * attempt)

        return page_num, None, last_err

    def download_chapter(
        self,
        chapter_input: str,
        output_dir: Path,
        workers: int = 5,
        use_proxy: bool = False,
        make_cbz: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Unduh semua halaman gambar dari satu chapter ke folder lokal (dan opsional arsip .cbz)."""
        chap_data = self.get_chapter_images(chapter_input)
        if not chap_data or not chap_data["images"]:
            print(f"[!] Chapter tidak ditemukan atau tidak memiliki gambar: {chapter_input}", file=sys.stderr)
            return None

        folder_name = sanitize_filename(chap_data["title"])
        chapter_dir = output_dir / folder_name
        chapter_dir.mkdir(parents=True, exist_ok=True)

        # Simpan metadata chapter
        (chapter_dir / "chapter_info.json").write_text(
            json.dumps(chap_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        total = chap_data["total_pages"]
        print(f"[*] Mengunduh '{chap_data['title']}' ({total} halaman) -> {chapter_dir}")

        success_files: List[Path] = []
        failed_pages: List[Tuple[int, str]] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._download_single_image, img, chapter_dir, use_proxy): img
                for img in chap_data["images"]
            }
            done_count = 0
            for future in concurrent.futures.as_completed(futures):
                done_count += 1
                page_num, saved_path, err = future.result()
                if saved_path:
                    success_files.append(saved_path)
                    print(f"    [{done_count}/{total}] Halaman {page_num:03d} OK ({saved_path.name})")
                else:
                    failed_pages.append((page_num, err or "Unknown error"))
                    print(f"    [{done_count}/{total}] Halaman {page_num:03d} GAGAL: {err}", file=sys.stderr)

        cbz_path = None
        if make_cbz and success_files:
            cbz_path = output_dir / f"{folder_name}.cbz"
            with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for img_file in sorted(success_files):
                    zf.write(img_file, arcname=img_file.name)
            print(f"[+] Arsip CBZ dibuat: {cbz_path}")

        return {
            "title": chap_data["title"],
            "directory": str(chapter_dir),
            "cbz_file": str(cbz_path) if cbz_path else None,
            "total_pages": total,
            "downloaded": len(success_files),
            "failed": failed_pages,
        }


def save_output(data: Any, output_path: Optional[str]) -> None:
    """Simpan data ke file JSON atau CSV (atau tampilkan ke stdout jika tidak ada output_path)."""
    if not output_path:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if out.suffix.lower() == ".csv" and isinstance(data, list) and data:
        # Flatten list/dict sederhana untuk CSV
        rows = []
        for item in data:
            flat = {}
            for k, v in item.items():
                if isinstance(v, (list, dict)):
                    flat[k] = json.dumps(v, ensure_ascii=False)
                else:
                    flat[k] = v
            rows.append(flat)
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"[+] Data berhasil disimpan ke CSV: {out} ({len(rows)} baris)")
    else:
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[+] Data berhasil disimpan ke JSON: {out}")


def filter_chapters(
    chapters: List[Dict[str, Any]],
    limit: Optional[int] = None,
    chapter_range: Optional[str] = None,
    reverse: bool = False,
) -> List[Dict[str, Any]]:
    """Filter daftar chapter berdasarkan nomor chapter atau jumlah limit."""
    selected = list(chapters)
    if reverse:
        # Default dari API biasanya chapter terbaru di atas; reverse membuatnya urut dari Chapter 1
        selected.reverse()

    if chapter_range:
        # Contoh: "1-5" atau "10" atau "1,3,5"
        target_nums = set()
        range_bounds: List[Tuple[float, float]] = []
        for part in chapter_range.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                try:
                    range_bounds.append((float(a), float(b)))
                except ValueError:
                    pass
            else:
                try:
                    target_nums.add(float(part))
                except ValueError:
                    pass

        filtered = []
        for ch in selected:
            m = re.search(r"(\d+(?:\.\d+)?)", ch.get("title", ""))
            if not m:
                continue
            num = float(m.group(1))
            in_range = any(low <= num <= high for low, high in range_bounds)
            if num in target_nums or in_range:
                filtered.append(ch)
        selected = filtered

    if limit and limit > 0:
        selected = selected[:limit]

    return selected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scraper & Downloader KomikUp (https://www.komikup.com/)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. newest
    p_newest = subparsers.add_parser("newest", help="Scrape daftar komik update terbaru")
    p_newest.add_argument("-p", "--pages", type=int, default=1, help="Jumlah halaman yang diambil (default: 1)")
    p_newest.add_argument("-o", "--output", help="Path file output (.json atau .csv)")

    # 2. list
    p_list = subparsers.add_parser("list", help="Scrape daftar komik berdasarkan tipe (manga/manhwa/manhua)")
    p_list.add_argument(
        "-t", "--type", default="manga", choices=["manga", "manhwa", "manhua"], help="Tipe komik (default: manga)"
    )
    p_list.add_argument("-l", "--letter", default="", help="Filter abjad A-Z (opsional)")
    p_list.add_argument("-p", "--pages", type=int, default=1, help="Jumlah halaman yang diambil (default: 1)")
    p_list.add_argument(
        "--with-details",
        action="store_true",
        help="Sekaligus ambil metadata lengkap (sinopsis, genre, rating, semua chapter) untuk setiap komik",
    )
    p_list.add_argument("-o", "--output", help="Path file output (.json atau .csv)")

    # 3. search
    p_search = subparsers.add_parser("search", help="Cari komik berdasarkan kata kunci")
    p_search.add_argument("query", help="Kata kunci judul komik")
    p_search.add_argument("--with-details", action="store_true", help="Ambil detail lengkap tiap hasil pencarian")
    p_search.add_argument("-o", "--output", help="Path file output (.json atau .csv)")

    # 4. top
    p_top = subparsers.add_parser("top", help="Scrape daftar komik terpopuler (daily, weekly, monthly)")
    p_top.add_argument("-o", "--output", help="Path file output (.json)")

    # 5. detail
    p_detail = subparsers.add_parser("detail", help="Scrape detail komik & seluruh daftar chapter")
    p_detail.add_argument("comic", help="URL detail komik atau slug komik (contoh: 'one-piece' atau URL penuh)")
    p_detail.add_argument("-o", "--output", help="Path file output (.json)")

    # 6. chapter
    p_chapter = subparsers.add_parser("chapter", help="Scrape daftar gambar halaman dari 1 chapter (dan opsional unduh)")
    p_chapter.add_argument("chapter", help="URL chapter atau slug chapter (contoh: '/big-shining-chapter-20/')")
    p_chapter.add_argument("-d", "--download", metavar="DIR", help="Unduh semua gambar chapter ke folder tujuan")
    p_chapter.add_argument("-w", "--workers", type=int, default=5, help="Jumlah thread unduhan paralel (default: 5)")
    p_chapter.add_argument("--cbz", action="store_true", help="Bungkus hasil unduhan menjadi file komik .cbz")
    p_chapter.add_argument("--proxy", action="store_true", help="Utamakan proxy serveproxy.com saat mengunduh gambar")
    p_chapter.add_argument("-o", "--output", help="Path file output JSON untuk daftar URL gambar")

    # 7. download (full comic downloader)
    p_dl = subparsers.add_parser(
        "download", help="Unduh komik lengkap (metadata JSON, cover, dan gambar halaman per chapter)"
    )
    p_dl.add_argument("comic", help="URL komik atau slug komik (contoh: 'big-shining' atau URL penuh)")
    p_dl.add_argument(
        "-d", "--dir", default="downloads", help="Folder induk penyimpanan unduhan (default: ./downloads)"
    )
    p_dl.add_argument(
        "-c",
        "--chapters",
        help="Filter nomor chapter yang diunduh, misal '1-5' atau '1,3,10' (default: semua atau sesuai --limit)",
    )
    p_dl.add_argument(
        "-n", "--limit", type=int, default=0, help="Batasi jumlah chapter yang diunduh (0 = semua yang cocok)"
    )
    p_dl.add_argument(
        "--from-start",
        action="store_true",
        help="Urutkan pengambilan mulai dari chapter awal (Chapter 1 ke atas)",
    )
    p_dl.add_argument("-w", "--workers", type=int, default=5, help="Jumlah thread unduhan gambar paralel (default: 5)")
    p_dl.add_argument("--cbz", action="store_true", help="Buat file .cbz untuk setiap chapter yang diunduh")
    p_dl.add_argument("--proxy", action="store_true", help="Utamakan proxy serveproxy.com saat mengunduh gambar")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    scraper = KomikUpScraper()

    if args.command == "newest":
        all_items = []
        for p in range(1, args.pages + 1):
            print(f"[*] Mengambil komik terbaru halaman {p}...", file=sys.stderr)
            items = scraper.get_newest(page=p)
            if not items:
                break
            all_items.extend(items)
        save_output(all_items, args.output)

    elif args.command == "list":
        all_items = []
        for p in range(1, args.pages + 1):
            print(
                f"[*] Mengambil daftar {args.type} (abjad='{args.letter or 'Semua'}') halaman {p}...",
                file=sys.stderr,
            )
            items = scraper.get_comic_list(comic_type=args.type, page=p, letter=args.letter)
            if not items:
                break
            all_items.extend(items)

        if args.with_details and all_items:
            detailed_items = []
            for idx, item in enumerate(all_items, start=1):
                print(f"    [{idx}/{len(all_items)}] Mengambil detail: {item['title']}...", file=sys.stderr)
                detail = scraper.get_comic_detail(item["endpoint"], known_type=item.get("type", ""))
                detailed_items.append(detail if detail else item)
            all_items = detailed_items

        save_output(all_items, args.output)

    elif args.command == "search":
        items = scraper.search(args.query)
        if args.with_details and items:
            detailed = []
            for idx, item in enumerate(items, start=1):
                print(f"    [{idx}/{len(items)}] Mengambil detail: {item['title']}...", file=sys.stderr)
                detail = scraper.get_comic_detail(item["endpoint"], known_type=item.get("type", ""))
                detailed.append(detail if detail else item)
            items = detailed
        save_output(items, args.output)

    elif args.command == "top":
        data = scraper.get_top_comics()
        save_output(data, args.output)

    elif args.command == "detail":
        detail = scraper.get_comic_detail(args.comic)
        if not detail:
            print(f"[!] Komik tidak ditemukan: {args.comic}", file=sys.stderr)
            sys.exit(1)
        save_output(detail, args.output)

    elif args.command == "chapter":
        if args.download:
            res = scraper.download_chapter(
                args.chapter,
                output_dir=Path(args.download),
                workers=args.workers,
                use_proxy=args.proxy,
                make_cbz=args.cbz,
            )
            if args.output and res:
                save_output(res, args.output)
        else:
            chap_data = scraper.get_chapter_images(args.chapter)
            if not chap_data:
                print(f"[!] Chapter tidak ditemukan: {args.chapter}", file=sys.stderr)
                sys.exit(1)
            save_output(chap_data, args.output)

    elif args.command == "download":
        print(f"[*] Mengambil informasi komik: {args.comic}...")
        detail = scraper.get_comic_detail(args.comic)
        if not detail:
            print(f"[!] Komik tidak ditemukan: {args.comic}", file=sys.stderr)
            sys.exit(1)

        comic_folder = Path(args.dir) / sanitize_filename(detail["title"])
        comic_folder.mkdir(parents=True, exist_ok=True)

        # Simpan metadata komik & daftar chapter
        info_path = comic_folder / "comic_info.json"
        info_path.write_text(json.dumps(detail, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[+] Metadata komik disimpan: {info_path} (Total: {detail['total_chapters']} chapter)")

        # Unduh cover komik jika ada
        if detail.get("cover_url"):
            cover_info = {
                "page": 0,
                "direct_url": detail["cover_url"],
                "proxied_url": detail["proxied_cover_url"],
            }
            _, saved_cover, _ = scraper._download_single_image(cover_info, comic_folder, use_proxy=args.proxy)
            if saved_cover:
                cover_dest = comic_folder / f"cover{saved_cover.suffix}"
                if saved_cover != cover_dest:
                    saved_cover.replace(cover_dest)
                print(f"[+] Cover komik diunduh: {cover_dest}")

        chapters_to_dl = filter_chapters(
            detail["chapters"],
            limit=args.limit if args.limit > 0 else None,
            chapter_range=args.chapters,
            reverse=args.from_start,
        )

        print(f"[*] Akan mengunduh {len(chapters_to_dl)} chapter ke {comic_folder}...")
        for idx, ch in enumerate(chapters_to_dl, start=1):
            print(f"\n--- [{idx}/{len(chapters_to_dl)}] {ch['title']} ---")
            scraper.download_chapter(
                ch["endpoint"],
                output_dir=comic_folder,
                workers=args.workers,
                use_proxy=args.proxy,
                make_cbz=args.cbz,
            )

        print(f"\n[✓] Selesai! Semua data tersimpan di: {comic_folder}")


if __name__ == "__main__":
    main()
