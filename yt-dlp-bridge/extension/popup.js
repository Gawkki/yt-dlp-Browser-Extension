const $ = (id) => document.getElementById(id);
const send = (msg) => new Promise((resolve) => chrome.runtime.sendMessage(msg, (r) => {
  void chrome.runtime.lastError;
  resolve(r || {});
}));

const SETTINGS = ["format", "cookies", "outdir"];
const ACTIVE = ["starting", "running", "cancelling"];
const rows = new Map(); // job id -> { li, name, cancel, fill, meta }

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function cookieDomain(host) {
  const parts = host.split(".");
  if (parts.length <= 2) return host;
  const n = parts.length;
  const second = new Set(["co", "com", "org", "net", "gov", "ac", "edu"]);
  return parts.slice(second.has(parts[n - 2]) && parts[n - 1].length === 2 ? -3 : -2).join(".");
}

function showNote(text) {
  $("note").textContent = text || "";
  $("note").hidden = !text;
}

// Rows are created once and updated in place, so buttons are never replaced under the cursor.
function makeRow(j) {
  const li = el("li");
  const top = el("div", "top");
  const name = el("span", "name");
  const cancel = el("button", "link", "Cancel");
  cancel.type = "button";
  cancel.addEventListener("click", async () => {
    cancel.disabled = true;
    cancel.textContent = "Cancelling…";
    await send({ type: "cancel", id: j.id });
    refresh();
  });
  top.append(name, cancel);
  const bar = el("div", "bar");
  const fill = el("i");
  bar.append(fill);
  const meta = el("div", "meta");
  li.append(top, bar, meta);
  return { li, name, cancel, fill, meta };
}

function setText(node, text) {
  if (node.textContent !== text) node.textContent = text;
}

function render(state) {
  const host = $("host");
  if (state.hostInfo) {
    const h = state.hostInfo;
    const bits = [h.ytdlp_version ? "yt-dlp " + h.ytdlp_version : "yt-dlp not found"];
    if (!h.ffmpeg) bits.push("ffmpeg missing");
    setText(host, "Helper connected · " + bits.join(" · "));
    host.className = "host " + (h.ytdlp_version ? "ok" : "bad");
  } else if (state.hostError) {
    setText(host, state.hostError);
    host.className = "host bad";
  } else {
    setText(host, "Checking helper…");
    host.className = "host";
  }

  const list = $("jobs");
  const jobs = state.jobs || [];
  const seen = new Set(jobs.map((j) => j.id));
  for (const [id, r] of rows) {
    if (!seen.has(id)) { r.li.remove(); rows.delete(id); }
  }

  let ref = list.firstChild;
  let finished = false;
  for (const j of jobs) {
    let r = rows.get(j.id);
    if (!r) { r = makeRow(j); rows.set(j.id, r); }
    if (r.li !== ref) list.insertBefore(r.li, ref); else ref = ref.nextSibling;

    const active = ACTIVE.includes(j.status);
    if (!active) finished = true;
    setText(r.name, j.file ? j.file.split(/[\\/]/).pop() : j.url);
    r.fill.style.width = (j.percent || 0) + "%";
    r.cancel.hidden = !active;
    if (j.status === "cancelling") { r.cancel.disabled = true; setText(r.cancel, "Cancelling…"); }

    let text, cls = "meta";
    if (j.status === "error") { text = j.error || "Failed"; cls = "meta err"; }
    else if (j.status === "done") text = "Saved to " + (j.outdir || "your downloads folder");
    else if (j.status === "cancelled") text = "Cancelled";
    else if (j.status === "cancelling") text = "Cancelling…";
    else if (j.status === "starting") text = "Starting…";
    else text = [Math.round(j.percent || 0) + "%", j.speed, j.eta && "ETA " + j.eta].filter(Boolean).join(" · ") || j.log || "Working…";
    setText(r.meta, text);
    r.meta.className = cls;
  }
  $("clear").hidden = !finished;
}

async function refresh() {
  render(await send({ type: "state" }));
}

function requestOrigins(origins) {
  return new Promise((resolve) => chrome.permissions.request({ origins }, (ok) => {
    void chrome.runtime.lastError;
    resolve(!!ok);
  }));
}

async function init() {
  chrome.storage.local.get({ format: "best", cookies: "", outdir: "" }, (s) => {
    for (const k of SETTINGS) $(k).value = s[k];
  });
  for (const k of SETTINGS) {
    $(k).addEventListener("change", () => chrome.storage.local.set({ [k]: $(k).value.trim() }));
  }

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const url = tabs && tabs[0] && tabs[0].url;
    if (url && /^https?:/i.test(url)) $("url").value = url;
  });

  $("go").addEventListener("click", async () => {
    showNote("");
    const url = $("url").value.trim();
    if (!/^https?:\/\//i.test(url)) {
      $("url").focus();
      return;
    }
    const cookies = $("cookies").value;
    if (cookies === "extension") {
      // Must be the first thing in the click handler: the browser only shows the
      // permission prompt while the click is still "fresh".
      let domain;
      try { domain = cookieDomain(new URL(url).hostname); } catch (e) { showNote("That link is not valid."); return; }
      const ok = await requestOrigins(["*://*." + domain + "/*"]);
      if (!ok) {
        showNote("Cookie access for " + domain + " was not allowed, so the download was not started.");
        return;
      }
    }
    const outdir = $("outdir").value.trim();
    chrome.storage.local.set({ format: $("format").value, cookies, outdir });
    await send({ type: "start", url, format: $("format").value, cookies, outdir });
    refresh();
  });

  $("clear").addEventListener("click", async () => { await send({ type: "clear" }); refresh(); });

  await send({ type: "ping" });
  await refresh();
  setInterval(refresh, 600);
}

init();
