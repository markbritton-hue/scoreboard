// Shared by the overlay (mascot.html) and the setup page (setup.html). Runs entirely in the
// browser, so it works from GitHub Pages as well as from a local server.
const SB = (() => {
  const SHEET_ID = "1o4IOGoVeV1ljEpoNxnMS56SN_hezE266Gvr7_GhYB9k";
  const CSV_URL = "https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/export?format=csv&gid=0";
  const MHSAA_URL = "https://my.mhsaa.com/DesktopModules/MHSAA-Endpoint/handlers/ContestWithParticipantDepotSearch.ashx";
  const DEFAULTS = { source: "mhsaa", date: "", hidden: [], extras: [], logos: {} };

  // ---- settings: defaults < Graphics/settings.json < ?cfg= in the page address ----
  function encodeCfg(cfg) {
    const bytes = new TextEncoder().encode(JSON.stringify(cfg));
    let bin = "";
    bytes.forEach(b => bin += String.fromCharCode(b));
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function decodeCfg(text) {
    const bin = atob(text.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(new TextDecoder().decode(Uint8Array.from(bin, c => c.charCodeAt(0))));
  }

  async function getJson(path, fallback) {
    try {
      const r = await fetch(path + "?_=" + Date.now(), { cache: "no-store" });
      return r.ok ? await r.json() : fallback;
    } catch (e) { return fallback; }
  }

  async function loadConfig() {
    const cfg = { ...DEFAULTS, ...(await getJson("Graphics/settings.json", {})) };
    const extras = await getJson("Graphics/extra_schools.json", []);
    cfg.extras = [...new Set([...(cfg.extras || []), ...extras])];
    if (cfg.source === "maxpreps") cfg.source = "mhsaa";
    const param = new URLSearchParams(location.search).get("cfg");
    if (param) {
      try { Object.assign(cfg, decodeCfg(param)); } catch (e) { console.error("Bad cfg parameter", e); }
    }
    return cfg;
  }

  async function loadLogos(cfg) {
    const logos = await getJson("Graphics/logos.json", {});
    return { ...logos, ...Object.fromEntries(Object.entries(cfg.logos || {}).map(([k, v]) => [k.toLowerCase(), v])) };
  }

  // ---- the Google Sheet ----
  function parseCSVLine(line) {
    const cells = [];
    let cur = "", inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (inQuotes) {
        if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; }
        else if (c === '"') inQuotes = false;
        else cur += c;
      } else if (c === '"') inQuotes = true;
      else if (c === ",") { cells.push(cur); cur = ""; }
      else cur += c;
    }
    cells.push(cur);
    return cells;
  }

  async function sheetLines() {
    const res = await fetch(CSV_URL + "&_=" + Date.now(), { cache: "no-store" });
    if (!res.ok) throw new Error("Sheet HTTP " + res.status);
    return (await res.text()).split(/\r?\n/).slice(1).map(l => parseCSVLine(l)[0] || "");
  }

  // School names mentioned in the sheet, in order of appearance.
  async function sheetTeams() {
    const teams = [];
    for (let text of await sheetLines()) {
      text = text.trim().replace(/\s+\(.*?\)\s*$/, "").replace(/\s+play\s+\w+.*$/i, "");
      for (const side of text.split(/\s+vs\.?\s+/i)) {
        const name = side.replace(/[\s-]+\d+\s*$/, "").trim().replace(/^vs\.?\s+/i, "");
        if (name && !teams.some(t => t.toLowerCase() === name.toLowerCase())) teams.push(name);
      }
    }
    return teams;
  }

  async function trackedSchools(cfg) {
    const teams = await sheetTeams();
    for (const x of cfg.extras || []) if (!teams.some(t => t.toLowerCase() === x.toLowerCase())) teams.push(x);
    return teams;
  }

  // ---- MHSAA score center ----
  function norm(name) {
    return name.toLowerCase().replace(/st\./g, "st").replace(/saint/g, "st").split(/[^a-z0-9]+/).filter(Boolean).join(" ");
  }

  // MHSAA sometimes uses a longer form ("North Adams-Jerome", "Adrian Lenawee Christian").
  function findTracked(name, tracked) {
    if (tracked.has(name)) return name;
    const keys = [...tracked.keys()].sort((a, b) => b.length - a.length);
    return keys.find(k => name.startsWith(k + " ")) || null;
  }

  function mdy(d) {
    return String(d.getMonth() + 1).padStart(2, "0") + "/" + String(d.getDate()).padStart(2, "0") + "/" + d.getFullYear();
  }

  // The game day: the date chosen on the setup page, otherwise the most recent Friday (today if it is Friday).
  function gameDay(cfg) {
    if (cfg.date) {
      const [y, m, d] = cfg.date.split("-").map(Number);
      return new Date(y, m - 1, d);
    }
    const day = new Date();
    day.setHours(0, 0, 0, 0);
    day.setDate(day.getDate() - ((day.getDay() + 2) % 7));
    return day;
  }

  async function fetchMhsaaGames(cfg, teamNames) {
    const day = gameDay(cfg);
    const urls = ["BFB", "B8F"].map(sport => // 11-player and 8-player football
      `${MHSAA_URL}?Method=ScoreCenterSearch&StartDate=${mdy(day)}&EndDate=${mdy(day)}&Level=&Sport=${sport}` +
      "&SchoolName=&Conference=&NoScore=&PostSeason=&ViewType=");
    const rows = (await Promise.all(urls.map(async u => {
      const r = await fetch(u);
      if (!r.ok) throw new Error("MHSAA HTTP " + r.status);
      return r.json();
    }))).flat();

    const tracked = new Map(teamNames.map(t => [norm(t), t]));
    const matched = new Set(), seen = new Set(), games = [];
    for (const r of rows) {
      if (r.LevelTypeDesc !== "Varsity") continue;
      const dupe = [r.HostTeamName, r.AwayTeamName, r.StartDate.slice(0, 10)].join("|");
      if (seen.has(dupe)) continue; // a rescheduled game is sometimes listed twice
      seen.add(dupe);
      const h = findTracked(norm(r.HostTeamName), tracked), a = findTracked(norm(r.AwayTeamName), tracked);
      if (!h && !a) continue;
      [h, a].forEach(x => x && matched.add(x));
      const date = new Date(r.StartDate);
      const hs = String(r.HostScore ?? "").trim(), as = String(r.AwayScore ?? "").trim();
      const played = hs !== "" && as !== "";
      const status = (r.StatusText || "").trim();
      games.push({
        id: String(r.SportContestId),
        date: r.StartDate,
        home: { team: h ? tracked.get(h) : r.HostTeamName, score: played ? hs : null },
        away: { team: a ? tracked.get(a) : r.AwayTeamName, score: played ? as : null },
        note: (["Dispute Score", "Submit Score"].includes(status) ? "" : status) ||
              (played ? "Final" : date.toLocaleDateString([], { weekday: "short" }) + " " +
                date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }))
      });
    }
    games.sort((x, y) => x.date.localeCompare(y.date));
    const missing = [...tracked].filter(([k]) => !matched.has(k)).map(([, t]) => t);
    return { games, missing, day };
  }

  return { DEFAULTS, encodeCfg, decodeCfg, loadConfig, loadLogos, parseCSVLine, sheetLines, sheetTeams,
           trackedSchools, fetchMhsaaGames, norm };
})();
