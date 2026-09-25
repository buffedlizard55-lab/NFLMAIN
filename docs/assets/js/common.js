/* ==========================================================================
   NFLMAIN - shared client library.

   Rules inherited from PROJECT_PROMPT.md:
     R2  A missing value renders as an em dash. It is NEVER rendered as 0, "" or a
         guess, because 0 points and "unknown" are different facts.
     R3  Every rendered figure can be traced to the provenance block in its JSON.
     R4  Irregularities recorded by the pipeline are surfaced in the UI, not hidden.

   No frameworks, no build step, no third-party requests other than the nfl.com club
   logo images (which degrade to initials if blocked).
   ========================================================================== */
(function (global) {
  "use strict";

  var DASH = "\u2014"; // em dash: "we do not know"
  var BASE = (function () {
    // Works both at https://user.github.io/NFLMAIN/ and from a local static server
    // rooted at docs/. Everything below is relative to the page.
    var p = global.location.pathname.replace(/[^/]*$/, "");
    return p;
  })();

  var cache = new Map();

  /* ------------------------------------------------------------- fetching */

  function dataUrl(rel) {
    return BASE + "data/" + rel;
  }

  /**
   * Fetch a JSON document from our own generated data directory.
   * Adds a cache-buster so a freshly committed snapshot is picked up immediately;
   * GitHub Pages CDN can otherwise serve a stale copy for a while.
   */
  function getJson(rel, opts) {
    opts = opts || {};
    var url = dataUrl(rel);
    var key = opts.fresh ? url + "?t=" + Date.now() : url;
    if (!opts.fresh && cache.has(key)) return Promise.resolve(cache.get(key));
    return fetch(key, { headers: { Accept: "application/json" }, cache: opts.fresh ? "no-store" : "default" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status + " for " + rel);
        return r.json();
      })
      .then(function (j) { cache.set(url, j); return j; });
  }

  function getManifest() { return getJson("manifest.json"); }
  function getTeams() {
    return getJson("teams.json").then(function (d) { return (d && d.teams) || {}; });
  }
  function getIndex() { return getJson("seasons/index.json"); }
  function getSeason(season) { return getJson("seasons/" + season + ".json"); }
  function getScoreboard() { return getJson("scoreboard.json"); }
  function getGame(gameId) { return getJson("pbp/" + encodeURIComponent(gameId) + ".json"); }
  function getLinkCheck() {
    return getJson("link-check.json").catch(function () { return null; });
  }

  /* ---------------------------------------------------------- formatting */

  /** A number that may legitimately be unknown. Never coerce null -> 0. */
  function num(v) {
    return (v === null || v === undefined || v === "") ? DASH : String(v);
  }

  /** A score. Unknown score and a score of zero must look different. */
  function score(v) {
    return (v === null || v === undefined) ? DASH : String(v);
  }

  function text(v) {
    return (v === null || v === undefined || v === "") ? DASH : String(v);
  }

  function pct(n, d) {
    if (!d) return DASH;
    return (Math.round((n / d) * 1000) / 10) + "%";
  }

  var STATUS_LABEL = {
    FINAL: "Final",
    IN_PROGRESS: "Live",
    SCHEDULED: "Scheduled",
    UNKNOWN: "Unknown"
  };

  function statusClass(s) {
    if (s === "IN_PROGRESS") return "badge--live";
    if (s === "FINAL") return "badge--final";
    if (s === "SCHEDULED") return "badge--sched";
    return "badge--unknown";
  }

  function statusLabel(g) {
    if (!g) return DASH;
    var base = STATUS_LABEL[g.status] || g.status || DASH;
    if (g.status === "FINAL" && g.overtime) base = "Final OT";
    return base;
  }

  /** Local, human kickoff string. Returns DASH when upstream has no kickoff time. */
  function kickoff(g, withDate) {
    if (!g || !g.kickoff_utc) {
      // We do have an upstream gameday even when the clock is missing.
      if (g && g.gameday) return g.gameday + (g.gametime_eastern ? " " + g.gametime_eastern + " ET" : "");
      return DASH;
    }
    var d = new Date(g.kickoff_utc);
    if (isNaN(d.getTime())) return DASH;
    var time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    if (!withDate) return time;
    return d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }) + " \u00b7 " + time;
  }

  function relativeTime(isoStr) {
    if (!isoStr) return DASH;
    var d = new Date(isoStr);
    if (isNaN(d.getTime())) return DASH;
    var secs = Math.round((Date.now() - d.getTime()) / 1000);
    if (secs < 0) return "in " + humanDuration(-secs);
    return humanDuration(secs) + " ago";
  }

  function humanDuration(secs) {
    if (secs < 60) return secs + "s";
    var m = Math.floor(secs / 60);
    if (m < 60) return m + "m";
    var h = Math.floor(m / 60);
    if (h < 48) return h + "h " + (m % 60) + "m";
    return Math.floor(h / 24) + "d";
  }

  function seasonTypeLabel(t) {
    if (t === "REG") return "Regular season";
    if (t === "POST") return "Postseason";
    if (t === "PRE") return "Preseason";
    return text(t);
  }

  function matchupText(g) {
    var a = (g.away && g.away.abbr) || "?";
    var h = (g.home && g.home.abbr) || "?";
    return a + " @ " + h;
  }

  /* -------------------------------------------------------------- logos */

  /**
   * Club logo with a two-step fallback: official nfl.com asset -> wikipedia asset ->
   * initials. Never leaves a broken image icon on screen.
   */
  function logoEl(team, sizeClass) {
    var abbr = (team && team.abbr) || null;
    var cls = "logo" + (sizeClass ? " " + sizeClass : "");
    var srcs = [];
    if (team) {
      if (team.logo) srcs.push(team.logo);
      if (team.logo_fallback) srcs.push(team.logo_fallback);
    }
    if (!srcs.length) return initialsEl(abbr, sizeClass);

    var img = document.createElement("img");
    img.className = cls;
    img.alt = (team && team.name) ? team.name + " logo" : (abbr ? abbr + " logo" : "team logo");
    img.loading = "lazy";
    img.decoding = "async";
    img.width = sizeClass === "logo--lg" ? 52 : (sizeClass === "logo--sm" ? 20 : 28);
    img.height = img.width;
    var i = 0;
    img.addEventListener("error", function () {
      i += 1;
      if (i < srcs.length) { img.src = srcs[i]; }
      else {
        var ph = initialsEl(abbr, sizeClass);
        if (img.parentNode) img.parentNode.replaceChild(ph, img);
      }
    });
    img.src = srcs[0];
    return img;
  }

  function initialsEl(abbr, sizeClass) {
    var span = document.createElement("span");
    span.className = "logo-ph" + (sizeClass === "logo--lg" ? " logo-ph--lg" : "");
    span.textContent = abbr ? String(abbr).slice(0, 4) : "?";
    span.setAttribute("aria-hidden", "true");
    return span;
  }

  /* --------------------------------------------------------------- DOM */

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v === null || v === undefined || v === false) return;
        if (k === "class") node.className = v;
        else if (k === "text") node.textContent = v;
        else if (k === "html") node.innerHTML = v;
        else if (k.slice(0, 2) === "on" && typeof v === "function") node.addEventListener(k.slice(2), v);
        else node.setAttribute(k, v === true ? "" : String(v));
      });
    }
    (children || []).forEach(function (c) {
      if (c === null || c === undefined || c === false) return;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); return node; }

  function badgeFor(g) {
    var extra = (g && g.status_estimated) ? " (est.)" : "";
    return el("span", {
      class: "badge " + statusClass(g && g.status),
      title: (g && g.status_detail) || ""
    }, [statusLabel(g) + extra]);
  }

  function irregularityFlags(g) {
    var list = (g && g.irregularities) || [];
    if (!list.length) return null;
    return el("span", {
      class: "flag",
      title: "Flagged for review: " + list.join("; ")
    }, ["\u26a0 " + list.length + " flag" + (list.length > 1 ? "s" : "")]);
  }

  /* ------------------------------------------------------- link safety */

  /**
   * Hide a constructed nfl.com link when the automated checker proved it does not
   * resolve. Unchecked links are shown: the pattern itself was verified, and the
   * checker samples rather than exhaustively crawling nfl.com.
   */
  function linkIsBroken(linkCheck, url) {
    if (!linkCheck || !url) return false;
    var failed = linkCheck.failures || [];
    for (var i = 0; i < failed.length; i++) {
      if (failed[i] && failed[i].url === url) return true;
    }
    return false;
  }

  function nflLink(href, label, opts) {
    if (!href) return null;
    opts = opts || {};
    if (opts.linkCheck && linkIsBroken(opts.linkCheck, href)) {
      return el("span", {
        class: "linkbtn",
        title: "This official NFL link was checked and did not resolve, so it is hidden. See Sources page."
      }, [label + " \u26a0"]);
    }
    return el("a", {
      class: "linkbtn" + (opts.primary ? " linkbtn--nfl" : ""),
      href: href, target: "_blank", rel: "noopener noreferrer external",
      title: opts.title || ("Verify at NFL.com: " + href)
    }, [label]);
  }

  /* --------------------------------------------------- provenance strip */

  function provenanceNote(doc, linkCheck) {
    var p = doc && (doc.provenance || (doc.pbp && doc.pbp.provenance));
    if (!p) return null;
    return el("p", { class: "card__meta" }, [
      "Source: ",
      el("code", { text: p.source_id || "?" }),
      " \u00b7 upstream ",
      el("a", { href: p.upstream_url, target: "_blank", rel: "noopener noreferrer", text: "dataset" }),
      " \u00b7 verify at ",
      el("a", { href: p.official_review_url || "https://www.nfl.com/scores/", target: "_blank", rel: "noopener noreferrer", text: "NFL.com" })
    ]);
  }

  /* ----------------------------------------------------------- exports */

  global.NFL = {
    DASH: DASH,
    BASE: BASE,
    dataUrl: dataUrl,
    getJson: getJson,
    getManifest: getManifest,
    getTeams: getTeams,
    getIndex: getIndex,
    getSeason: getSeason,
    getScoreboard: getScoreboard,
    getGame: getGame,
    getLinkCheck: getLinkCheck,
    num: num,
    score: score,
    text: text,
    pct: pct,
    statusLabel: statusLabel,
    statusClass: statusClass,
    kickoff: kickoff,
    relativeTime: relativeTime,
    humanDuration: humanDuration,
    seasonTypeLabel: seasonTypeLabel,
    matchupText: matchupText,
    logoEl: logoEl,
    initialsEl: initialsEl,
    el: el,
    clear: clear,
    badgeFor: badgeFor,
    irregularityFlags: irregularityFlags,
    nflLink: nflLink,
    linkIsBroken: linkIsBroken,
    provenanceNote: provenanceNote,
    cache: cache
  };
})(window);
