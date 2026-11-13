// Server lokal sederhana (tanpa dependency) untuk menjalankan index.html & /api/proxy di localhost
const http = require("http");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

const PORT = process.env.PORT || 3000;
const PRIMARY_API = "https://api.komikup.com/api";
const FALLBACK_API = "https://api2.komikup.com/api";

const server = http.createServer(async (req, res) => {
  const parsedUrl = new URL(req.url, `http://localhost:${PORT}`);

  if (parsedUrl.pathname === "/api/proxy") {
    const ep = parsedUrl.searchParams.get("ep") || "/comic/newest/page/1";
    const cleanEp = ep.startsWith("/") ? ep : `/${ep}`;
    const headers = {
      "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
      Accept: "application/json",
      Origin: "https://www.komikup.com",
      Referer: "https://www.komikup.com/",
    };

    try {
      // Same order as api/proxy.js: search only works on api2.
      const [first, second] = cleanEp.startsWith("/comic/search/") ? [FALLBACK_API, PRIMARY_API] : [PRIMARY_API, FALLBACK_API];
      let apiRes = await fetch(`${first}${cleanEp}`, { headers });
      if (!apiRes.ok) {
        apiRes = await fetch(`${second}${cleanEp}`, { headers });
      }
      const data = await apiRes.text();
      res.writeHead(apiRes.status, {
        "Content-Type": "application/json; charset=utf-8",
        "Access-Control-Allow-Origin": "*",
      });
      return res.end(data);
    } catch (err) {
      res.writeHead(500, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ status: "error", message: err.message }));
    }
  }

  // Static files at the project root (icons, manifest, robots, sitemap), same as Vercel serves them.
  const STATIC = {
    "/favicon.ico": "image/x-icon",
    "/icon.svg": "image/svg+xml",
    "/icon-192.png": "image/png",
    "/icon-512.png": "image/png",
    "/icon-maskable-512.png": "image/png",
    "/apple-touch-icon.png": "image/png",
    "/og-image.png": "image/png",
    "/site.webmanifest": "application/manifest+json",
    "/robots.txt": "text/plain; charset=utf-8",
    "/sitemap.xml": "application/xml; charset=utf-8",
  };
  if (STATIC[parsedUrl.pathname]) {
    return fs.readFile(path.join(__dirname, parsedUrl.pathname), (err, content) => {
      if (err) { res.writeHead(404); return res.end(); }
      res.writeHead(200, { "Content-Type": STATIC[parsedUrl.pathname] });
      res.end(content);
    });
  }

  // Layani index.html
  const filePath = path.join(__dirname, "index.html");
  fs.readFile(filePath, (err, content) => {
    if (err) {
      res.writeHead(500);
      return res.end("Error loading index.html");
    }
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(content);
  });
});

server.listen(PORT, () => {
  console.log(`Server berjalan di http://localhost:${PORT}`);
});
