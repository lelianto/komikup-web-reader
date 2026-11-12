// Vercel Serverless Function: /api/proxy.js
// Meneruskan request dari frontend ke api.komikup.com dengan header Referer & Origin resmi

const PRIMARY_API = "https://api.komikup.com/api";
const FALLBACK_API = "https://api2.komikup.com/api";

const HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
  Accept: "application/json, text/plain, */*",
  "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
  Origin: "https://www.komikup.com",
  Referer: "https://www.komikup.com/",
};

// Search only works on api2 (api always answers 404), so ask api2 first there.
function apiOrder(ep) {
  return ep.startsWith("/comic/search/") ? [FALLBACK_API, PRIMARY_API] : [PRIMARY_API, FALLBACK_API];
}

// CDN cache per endpoint: chapter images never change, details change only when a chapter is added.
function cacheControl(ep, status) {
  if (status !== 200) return "public, s-maxage=30";
  if (ep.startsWith("/comic/chapter/")) return "public, s-maxage=86400, stale-while-revalidate=604800";
  if (ep.startsWith("/comic/info/")) return "public, s-maxage=600, stale-while-revalidate=3600";
  if (ep.startsWith("/comic/list")) return "public, s-maxage=1800, stale-while-revalidate=86400";
  if (ep.startsWith("/comic/search/")) return "public, s-maxage=900, stale-while-revalidate=3600";
  return "public, s-maxage=120, stale-while-revalidate=600";
}

export default async function handler(req, res) {
  // Izinkan CORS agar bisa diakses dari frontend
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  const endpoint = req.query.ep || "/comic/newest/page/1";
  const cleanEp = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;

  try {
    const [first, second] = apiOrder(cleanEp);
    let response = await fetch(`${first}${cleanEp}`, { headers: HEADERS });
    if (!response.ok) {
      response = await fetch(`${second}${cleanEp}`, { headers: HEADERS });
    }
    const data = await response.json();
    res.setHeader("Cache-Control", cacheControl(cleanEp, response.status));
    return res.status(response.status).json(data);
  } catch (error) {
    res.setHeader("Cache-Control", "no-store");
    return res.status(500).json({
      status: "error",
      message: error.message || "Gagal mengambil data dari API KomikUp",
    });
  }
}
