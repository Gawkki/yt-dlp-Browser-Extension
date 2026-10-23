// Works in Chrome (service worker) and Firefox (event page). Uses the callback-style
// `chrome.*` API, which both browsers support.
const HOST = "com.ytdlp_bridge.host";

let port = null;
let hostInfo = null;   // last pong from the host
let hostError = null;  // why the connection failed, if it did
const jobs = {};       // id -> { id, url, format, status, percent, speed, eta, file, error, log }

const NOT_FOUND_HELP =
  "Native host not found. Run `python install.py` from the yt-dlp-bridge folder, then fully restart the browser.";

function connect() {
  if (port) return port;
  const p = chrome.runtime.connectNative(HOST);
  port = p;
  hostError = null;

  p.onMessage.addListener(onHostMessage);
  p.onDisconnect.addListener(() => {
    const raw = (chrome.runtime.lastError && chrome.runtime.lastError.message) || (p.error && p.error.message) || "";
    if (port === p) port = null;
    hostInfo = null;
    hostError = /not found|forbidden|no such native/i.test(raw) ? NOT_FOUND_HELP + " (" + raw + ")" : raw || "Native host exited.";
    for (const j of Object.values(jobs)) {
      if (j.status === "running" || j.status === "starting" || j.status === "cancelling") {
        j.status = "error";
        j.error = hostError;
      }
    }
  });
  return p;
}

function onHostMessage(m) {
  if (m.type === "pong") { hostInfo = m; return; }
  const j = jobs[m.id];
  if (!j) return;
  switch (m.type) {
    case "started": if (j.status !== "cancelling") j.status = "running"; j.outdir = m.outdir; break;
    case "progress": if (j.status !== "cancelling") j.status = "running"; j.percent = m.percent; j.speed = m.speed; j.eta = m.eta; break;
    case "log": j.log = m.line; break;
    case "done":
      j.status = "done"; j.percent = 100; j.file = m.file; j.outdir = m.outdir;
      chrome.action.setBadgeBackgroundColor({ color: "#1f6f5c" });
      chrome.action.setBadgeText({ text: "✓" });
      break;
    case "cancelled": j.status = "cancelled"; break;
    case "error": j.status = "error"; j.error = m.error; break;
  }
}

// "example.co.uk" / "youtube.com" from a hostname (good enough for cookie scoping).
function cookieDomain(host) {
  const parts = host.split(".");
  if (parts.length <= 2) return host;
  const n = parts.length;
  const second = new Set(["co", "com", "org", "net", "gov", "ac", "edu"]);
  return parts.slice(second.has(parts[n - 2]) && parts[n - 1].length === 2 ? -3 : -2).join(".");
}

// Read the site's cookies straight from the browser and format them for yt-dlp (Netscape cookies.txt).
function getCookieText(url, cb) {
  let domain;
  try { domain = cookieDomain(new URL(url).hostname); } catch (e) { return cb(null, "Invalid link."); }
  const origins = ["*://*." + domain + "/*"];
  chrome.permissions.contains({ origins }, (ok) => {
    void chrome.runtime.lastError;
    if (!ok) {
      return cb(null, "No cookie permission for " + domain + ". Open the extension popup on this site and press Download once to allow it.");
    }
    chrome.cookies.getAll({ domain }, (list) => {
      void chrome.runtime.lastError;
      const session = Math.floor(Date.now() / 1000) + 365 * 86400;
      const lines = ["# Netscape HTTP Cookie File"];
      for (const c of list || []) {
        const dom = c.hostOnly ? c.domain : (c.domain.startsWith(".") ? c.domain : "." + c.domain);
        lines.push([
          (c.httpOnly ? "#HttpOnly_" : "") + dom,
          c.hostOnly ? "FALSE" : "TRUE",
          c.path,
          c.secure ? "TRUE" : "FALSE",
          c.expirationDate ? Math.floor(c.expirationDate) : session,
          c.name,
          c.value,
        ].join("\t"));
      }
      cb(lines.join("\n") + "\n", null);
    });
  });
}

function startDownload({ url, format, cookies, outdir }) {
  const id = Math.random().toString(36).slice(2, 10);
  jobs[id] = { id, url, format, status: "starting", percent: 0, speed: "", eta: "", log: "" };
  chrome.action.setBadgeText({ text: "" });

  const post = (extra) => {
    try {
      connect().postMessage({ action: "download", id, url, format, cookies, outdir, ...extra });
    } catch (e) {
      jobs[id].status = "error";
      jobs[id].error = String(e);
    }
  };

  if (cookies === "extension") {
    getCookieText(url, (text, err) => {
      if (err) { jobs[id].status = "error"; jobs[id].error = err; return; }
      post({ cookies: "", cookie_text: text });
    });
  } else {
    post({});
  }
  return id;
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "state") {
    sendResponse({ jobs: Object.values(jobs).slice(-8).reverse(), hostInfo, hostError });
  } else if (msg.type === "ping") {
    try { connect().postMessage({ action: "ping" }); } catch (e) { hostError = String(e); }
    sendResponse({ ok: true });
  } else if (msg.type === "start") {
    sendResponse({ id: startDownload(msg) });
  } else if (msg.type === "cancel") {
    const j = jobs[msg.id];
    if (j && (j.status === "running" || j.status === "starting")) {
      j.status = "cancelling";
      if (port) port.postMessage({ action: "cancel", id: msg.id });
      else j.status = "cancelled";
    }
    sendResponse({ ok: true });
  } else if (msg.type === "clear") {
    for (const [id, j] of Object.entries(jobs)) if (!["running", "starting", "cancelling"].includes(j.status)) delete jobs[id];
    sendResponse({ ok: true });
  }
  return true; // keep the channel open for sendResponse
});

// Right-click a link or page -> download with saved settings.
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "ytdlp-link", title: "Download link with yt-dlp", contexts: ["link"] });
  chrome.contextMenus.create({ id: "ytdlp-page", title: "Download this page with yt-dlp", contexts: ["page", "video"] });
});

chrome.contextMenus.onClicked.addListener((info) => {
  const url = info.menuItemId === "ytdlp-link" ? info.linkUrl : info.pageUrl;
  chrome.storage.local.get({ format: "best", cookies: "", outdir: "" }, (s) => {
    startDownload({ url, format: s.format, cookies: s.cookies, outdir: s.outdir });
  });
});
