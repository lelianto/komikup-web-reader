// Vercel Serverless Function: /api/proxy.js
// Meneruskan request dari frontend ke api.komikup.com dengan header Referer & Origin resmi

const PRIMARY_API = "https://api.komikup.com/api";
const FALLBACK_API = "https://api2.komikup.com/api";

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

  const headers = {
    "User-Agent":
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    Accept: "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    Origin: "https://www.komikup.com",
    Referer: "https://www.komikup.com/",
  };

  try {
    let response = await fetch(`${PRIMARY_API}${cleanEp}`, { headers });
    if (!response.ok) {
      response = await fetch(`${FALLBACK_API}${cleanEp}`, { headers });
    }
    const data = await response.json();
    res.setHeader("Cache-Control", "s-maxage=120, stale-while-revalidate=300");
    return res.status(response.status).json(data);
  } catch (error) {
    return res.status(500).json({
      status: "error",
      message: error.message || "Gagal mengambil data dari API KomikUp",
    });
  }
}
