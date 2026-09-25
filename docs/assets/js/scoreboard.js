/* ==========================================================================
   Scoreboard controller (docs/index.html)

   Reads only the generated snapshots in docs/data/. No third-party requests.
   ========================================================================== */
(function () {
  "use strict";

  var N = window.NFL;
  var state = {
    manifest: null,
    teams: {},
    index: null,
    linkCheck: null,
    seasonDoc: null,
    season: null,
    type: "REG",
    week: null,
    team: "",
    q: "",
    status: "",
    timer: null
  };

  var $ = function (id) { return document.getElementById(id); };

  /* ------------------------------------------------------------- URL sync */

  function readParams() {
    var p = new URLSearchParams(window.location.search);
    if (p.get("season")) state.season = parseInt(p.get("season"), 10) || null;
    if (p.get("type")) state.type = p.get("type").toUpperCase();
    if (p.get("week")) state.week = parseInt(p.get("week"), 10) || null;
    if (p.get("team")) state.team = p.get("team").toUpperCase();
    if (p.get("q")) state.q = p.get("q");
    if (p.get("status")) state.status = p.get("status");
  }

  function writeParams() {
    var p = new URLSearchParams();
    if (state.season) p.set("season", state.season);
    if (state.type) p.set("type", state.type);
    if (state.week) p.set("week", state.week);
    if (state.team) p.set("team", state.team);
    if (state.q) p.set("q", state.q);
    if (state.status) p.set("status", state.status);
    var qs = p.toString();
    var url = window.location.pathname + (qs ? "?" + qs : "");
    window.history.replaceState(null, "", url);
  }

  /* ---------------------------------------------------------- status bar */

  function renderStatusbar() {
    var bar = N.clear($("statusbar"));
    var m = state.manifest;
    if (!m) {
      bar.appendChild(N.el("span", { class: "pill pill--bad" }, ["No data snapshot found"]));
      return;
    }
    var games = (state.seasonDoc && state.seasonDoc.games) || [];
    var live = games.filter(function (g) { return g.status === "IN_PROGRESS"; }).length;
    var flags = games.reduce(function (n, g) { return n + ((g.irregularities || []).length); }, 0);

    var livePill = live > 0
      ? N.el("span", { class: "pill pill--live" }, [
          N.el("span", { class: "dot dot--pulse" }), live + " live"
        ])
      : N.el("span", { class: "pill" }, ["No games in progress"]);
    bar.appendChild(livePill);

    bar.appendChild(N.el("span", {
      class: "pill pill--ok",
      title: "Timestamp recorded by the pipeline when it fetched the upstream feed"
    }, ["Data as of " + N.relativeTime(m.generated_at)]));

    bar.appendChild(N.el("span", {
      class: "pill",
      title: "Upstream dataset this snapshot was built from"
    }, ["Source: nflverse mirror of nfl.com"]));

    if (m.coverage) {
      bar.appendChild(N.el("span", { class: "pill" }, [
        (m.coverage.season_min || "?") + "\u2013" + (m.coverage.season_max || "?") +
        " \u00b7 " + (m.coverage.game_count || 0).toLocaleString() + " games"
      ]));
    }

    if (flags > 0) {
      bar.appendChild(N.el("a", {
        class: "pill pill--warn", href: "sources.html#irregularities",
        title: "Open the verification report"
      }, ["\u26a0 " + flags + " flag" + (flags === 1 ? "" : "s") + " for review"]));
    }

    var api = m.official_api || {};
    if (api.available) {
      bar.appendChild(N.el("span", { class: "pill pill--ok" }, ["api.nfl.com cross-check: on"]));
    } else {
      bar.appendChild(N.el("a", {
        class: "pill pill--warn", href: "sources.html#official-api",
        title: api.reason || ""
      }, ["api.nfl.com cross-check: off"]));
    }

    // The direct read of nfl.com: what the league's own page said when this snapshot was
    // built, and whether it agreed. Only ever rendered from what the build actually did -
    // if the read failed, the pill says so instead of implying the scores were confirmed.
    var d = m.official_direct;
    if (d && d.attempted && d.weeks_read) {
      var agreed = d.score_mismatches === 0 && d.unrecognised_club_names === 0 &&
        d.official_unmatched === 0;
      bar.appendChild(N.el("a", {
        class: agreed ? "pill pill--ok" : "pill pill--bad",
        href: "sources.html#direct",
        title: "This build fetched " + d.weeks_read + " week page(s) from nfl.com itself " +
          "and compared them with these numbers: " + d.score_matches +
          " score(s) matched, " + d.score_mismatches + " disagreed." +
          (d.official_unmatched ? " " + d.official_unmatched + " game(s) nfl.com lists " +
            "are missing here." : "")
      }, ["nfl.com direct read: " + (agreed ? "\u2713 agreed" : "\u26a0 see differences")]));
    } else if (d && d.attempted) {
      bar.appendChild(N.el("a", {
        class: "pill pill--warn", href: "sources.html#direct",
        title: "The build tried to read nfl.com's own week page and could not use the " +
          "answer, so these scores have not been confirmed against the league."
      }, ["nfl.com direct read: unavailable"]));
    }
  }

  /* ------------------------------------------------------------- notices */

  function renderNotices() {
    var box = N.clear($("notices"));
    var m = state.manifest;
    if (!m) return;

    var irr = m.irregularities || {};
    if (irr.total) {
      var kinds = Object.keys(irr.by_kind || {}).slice(0, 6).map(function (k) {
        return k + " (" + irr.by_kind[k].count + ")";
      });
      box.appendChild(N.el("div", { class: "notice notice--warn" }, [
        N.el("h4", { text: "Irregularities flagged for review" }),
        N.el("div", { text: irr.total + " finding(s): " + kinds.join(", ") }),
        N.el("div", {}, [
          "Details and the official links used to check them are on the ",
          N.el("a", { href: "sources.html#irregularities", text: "Sources & verification" }),
          " page."
        ])
      ]));
    }

    var failed = (m.fetch_failures || []);
    if (failed.length) {
      box.appendChild(N.el("div", { class: "notice notice--bad" }, [
        N.el("h4", { text: "Upstream fetch failed" }),
        N.el("ul", {}, failed.map(function (f) {
          return N.el("li", {}, [f.url + " \u2014 " + f.error]);
        }))
      ]));
    }

    var lc = state.linkCheck;
    if (lc && lc.summary && lc.summary.failed) {
      box.appendChild(N.el("div", { class: "notice notice--warn" }, [
        N.el("h4", { text: "Some official NFL links did not resolve" }),
        N.el("div", { text: lc.summary.failed + " of " + lc.summary.requested +
          " checked link(s) failed. Those links are hidden in the UI rather than " +
          "shown broken. See " }),
        N.el("a", { href: "sources.html#links", text: "link verification" })
      ]));
    }
  }

  /* ------------------------------------------------------------ controls */

  function seasonsAvailable() {
    return ((state.index && state.index.seasons) || []).map(function (s) { return s.season; });
  }

  function renderSeasonSelect() {
    var sel = N.clear($("seasonSel"));
    seasonsAvailable().forEach(function (yr) {
      sel.appendChild(N.el("option", {
        value: yr, selected: yr === state.season ? true : null,
        text: (yr === state.season ? yr + " (current view)" : String(yr))
      }));
    });
    sel.value = String(state.season);
  }

  function typesForSeason() {
    var s = ((state.index && state.index.seasons) || []).filter(function (x) {
      return x.season === state.season;
    })[0];
    var keys = s ? Object.keys(s.season_types || {}) : [];
    if (!keys.length) keys = ["REG"];
    // Stable, familiar order.
    var order = ["PRE", "REG", "POST"];
    keys.sort(function (a, b) {
      var ia = order.indexOf(a), ib = order.indexOf(b);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });
    return keys;
  }

  function renderTypeSeg() {
    var seg = N.clear($("typeSeg"));
    var types = typesForSeason();
    if (types.indexOf(state.type) === -1) state.type = types[0];
    types.forEach(function (t) {
      seg.appendChild(N.el("button", {
        type: "button",
        "aria-pressed": t === state.type ? "true" : "false",
        onclick: function () { state.type = t; state.week = null; afterChange(); }
      }, [N.seasonTypeLabel(t).replace(" season", "")]));
    });
  }

  function renderTeamSelect() {
    var sel = N.clear($("teamSel"));
    sel.appendChild(N.el("option", { value: "", text: "All teams" }));
    var abbrs = Object.keys(state.teams).sort();
    abbrs.forEach(function (a) {
      var t = state.teams[a];
      sel.appendChild(N.el("option", {
        value: a, selected: a === state.team ? true : null,
        text: (t.name || a)
      }));
    });
    sel.value = state.team;
  }

  function weeksForType() {
    var games = (state.seasonDoc && state.seasonDoc.games) || [];
    var set = {};
    games.forEach(function (g) {
      if ((g.season_type || "") === state.type && g.week !== null && g.week !== undefined) {
        set[g.week] = (set[g.week] || 0) + 1;
      }
    });
    return Object.keys(set).map(Number).sort(function (a, b) { return a - b; });
  }

  function renderWeeknav() {
    var nav = N.clear($("weeknav"));
    var weeks = weeksForType();
    if (!weeks.length) return;
    if (state.week === null || weeks.indexOf(state.week) === -1) {
      // Default to the most interesting week: the latest with a live game, else the
      // latest with a final, else the earliest scheduled.
      var games = (state.seasonDoc && state.seasonDoc.games) || [];
      var liveWeeks = games.filter(function (g) {
        return g.season_type === state.type && g.status === "IN_PROGRESS";
      }).map(function (g) { return g.week; });
      var finalWeeks = games.filter(function (g) {
        return g.season_type === state.type && g.status === "FINAL";
      }).map(function (g) { return g.week; });
      if (liveWeeks.length) state.week = Math.max.apply(null, liveWeeks);
      else if (finalWeeks.length) state.week = Math.max.apply(null, finalWeeks);
      else state.week = weeks[0];
    }
    weeks.forEach(function (w) {
      var label = (state.type === "POST") ? playoffLabel(w) : ("Week " + w);
      nav.appendChild(N.el("button", {
        type: "button",
        "aria-pressed": w === state.week ? "true" : "false",
        onclick: function () { state.week = w; afterChange(); }
      }, [label]));
    });
  }

  // Postseason week numbers in the upstream feed are league week numbers, not round
  // names. We do not invent a round name we cannot verify, so label by week and show
  // the raw number.
  function playoffLabel(w) { return "Playoff wk " + w; }

  /* -------------------------------------------------------------- filter */

  function filteredGames() {
    var games = (state.seasonDoc && state.seasonDoc.games) || [];
    var q = state.q.trim().toLowerCase();
    return games.filter(function (g) {
      if ((g.season_type || "") !== state.type) return false;
      if (state.week !== null && g.week !== state.week) return false;
      if (state.team) {
        var a = g.away && g.away.abbr, h = g.home && g.home.abbr;
        if (a !== state.team && h !== state.team) return false;
      }
      if (state.status === "FLAGGED") {
        if (!(g.irregularities || []).length) return false;
      } else if (state.status && g.status !== state.status) {
        return false;
      }
      if (q) {
        var hay = [
          g.game_id, g.away && g.away.name, g.away && g.away.abbr,
          g.home && g.home.name, g.home && g.home.abbr,
          g.venue && g.venue.stadium,
          g.ids && g.ids.nfl_gsis_old_game_id
        ].filter(Boolean).join(" ").toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
  }

  /* ------------------------------------------------------------- render */

  function teamRow(team, isWinner, otherScore, myScore, showScore) {
    var cls = "teamrow";
    if (showScore && isWinner === true) cls += " teamrow--winner";
    else if (showScore && isWinner === false) cls += " teamrow--loser";
    var row = N.el("div", { class: cls });
    row.appendChild(N.logoEl(team));
    row.appendChild(N.el("div", { class: "teamrow__name" }, [
      N.el("span", { text: (team && team.name) || (team && team.abbr) || N.DASH }),
      N.el("span", { class: "teamrow__abbr", text: (team && team.abbr) || "" })
    ]));
    row.appendChild(N.el("div", { class: "teamrow__score" }, [
      showScore ? N.score(myScore) : N.kickoff({ kickoff_utc: null }, false) || ""
    ]));
    return row;
  }

  function quarterLine(g) {
    var qs = g.quarter_scores;
    if (!qs || !qs.labels || !qs.labels.length) return null;
    var head = N.el("tr", {}, [N.el("th", { text: "Team" })].concat(
      qs.labels.map(function (l) { return N.el("th", { text: l }); })
    ).concat([N.el("th", { text: "T" })]));

    function rowFor(label, line, total, team) {
      return N.el("tr", {}, [
        N.el("td", {}, [
          N.logoEl(team, "logo--sm"),
          " ",
          N.el("span", { text: label })
        ])
      ].concat(line.map(function (v) { return N.el("td", { text: N.num(v) }); }))
       .concat([N.el("td", { text: N.num(total), style: "font-weight:800" })]));
    }

    var t = N.el("table", {}, [
      N.el("thead", {}, [head]),
      N.el("tbody", {}, [
        rowFor((g.away && g.away.abbr) || "Away", qs.away, qs.away_total, g.away),
        rowFor((g.home && g.home.abbr) || "Home", qs.home, qs.home_total, g.home)
      ])
    ]);
    return N.el("div", { class: "qline", title: "Quarter-by-quarter, derived from the running score on each official play" }, [t]);
  }

  function gameCard(g) {
    var showScore = g.status !== "SCHEDULED";
    var awayScore = g.away ? g.away.score : null;
    var homeScore = g.home ? g.home.score : null;
    var awayWin = null, homeWin = null;
    if (showScore && awayScore !== null && homeScore !== null) {
      awayWin = awayScore > homeScore;
      homeWin = homeScore > awayScore;
    }

    var accent = (g.home && g.home.color) || (g.away && g.away.color) || null;
    var card = N.el("article", {
      class: "card" + (g.status === "IN_PROGRESS" ? " card--live" : ""),
      style: accent ? "--card-accent:" + accent : null
    });

    card.appendChild(N.el("div", { class: "card__top" }, [
      N.el("span", { class: "card__meta" }, [
        (g.season_type === "POST" ? playoffLabel(g.week) : "Week " + N.num(g.week)) +
        " \u00b7 " + N.kickoff(g, true)
      ]),
      N.badgeFor(g)
    ]));

    var body = N.el("div");
    body.appendChild(teamRow(g.away, awayWin, homeScore, awayScore, showScore));
    body.appendChild(teamRow(g.home, homeWin, awayScore, homeScore, showScore));
    if (!showScore) {
      body.appendChild(N.el("div", { class: "card__meta", style: "margin-top:6px" }, [
        "Kickoff " + N.kickoff(g, true)
      ]));
    }
    card.appendChild(body);

    var ql = quarterLine(g);
    if (ql) card.appendChild(ql);

    var flags = N.irregularityFlags(g);
    var foot = N.el("div", { class: "card__foot" });
    foot.appendChild(N.el("span", {
      class: "card__venue",
      title: [
        g.venue && g.venue.stadium,
        g.venue && g.venue.roof,
        g.venue && g.venue.surface,
        (g.venue && g.venue.temp_f !== null && g.venue.temp_f !== undefined) ? (g.venue.temp_f + "\u00b0F") : null,
        (g.venue && g.venue.wind_mph !== null && g.venue.wind_mph !== undefined) ? ("wind " + g.venue.wind_mph + " mph") : null,
        g.people && g.people.referee ? ("referee " + g.people.referee) : null
      ].filter(Boolean).join(" \u00b7 ")
    }, [flags || N.el("span", { text: (g.venue && g.venue.stadium) || "" })]));

    var links = N.el("span", { class: "card__links" });
    var detailHref = "game.html?id=" + encodeURIComponent(g.game_id || "") +
      "&season=" + encodeURIComponent(g.season || "");
    if (g.pbp_available) {
      links.appendChild(N.el("a", { class: "linkbtn", href: detailHref, text: "Play-by-play" }));
    } else {
      links.appendChild(N.el("a", { class: "linkbtn", href: detailHref, text: "Details" }));
    }
    var nfl = N.nflLink(g.links && g.links.nfl_game, "NFL.com", {
      primary: true, linkCheck: state.linkCheck,
      title: "Open the official NFL Game Center page for this game"
    });
    if (nfl) links.appendChild(nfl);
    foot.appendChild(links);
    card.appendChild(foot);

    return card;
  }

  function renderResults() {
    var box = N.clear($("results"));
    var games = filteredGames();

    var title = "Scoreboard";
    if (state.season) {
      title = N.seasonTypeLabel(state.type) + " \u00b7 " +
        (state.type === "POST" ? playoffLabel(state.week) : "Week " + (state.week === null ? "\u2014" : state.week)) +
        " \u00b7 " + state.season;
    }
    $("pageTitle").textContent = title;
    $("pageSub").textContent = games.length +
      " game" + (games.length === 1 ? "" : "s") +
      (state.team ? " for " + ((state.teams[state.team] || {}).name || state.team) : "") +
      (state.q ? " matching \u201c" + state.q + "\u201d" : "");

    if (!games.length) {
      box.appendChild(N.el("div", { class: "empty" }, [
        N.el("h3", { text: "No games match these filters" }),
        N.el("p", { text: "Try another week, clear the team filter, or pick a different season. " +
          "This is not an error \u2014 it means the upstream NFL schedule has no game " +
          "matching this combination." })
      ]));
      return;
    }

    var grid = N.el("div", { class: "grid" });
    games.forEach(function (g) { grid.appendChild(gameCard(g)); });
    box.appendChild(grid);

    var prov = state.seasonDoc && state.seasonDoc.provenance;
    if (prov) {
      box.appendChild(N.el("p", { class: "card__meta", style: "margin-top:14px" }, [
        "Provenance: ",
        N.el("code", { text: prov.source_id }),
        " \u00b7 ",
        N.el("a", { href: prov.upstream_url, target: "_blank", rel: "noopener noreferrer", text: "upstream dataset" }),
        " \u00b7 cross-check at ",
        N.el("a", { href: prov.official_review_url, target: "_blank", rel: "noopener noreferrer", text: "NFL.com/scores" }),
        " \u00b7 ",
        N.el("a", { href: "sources.html", text: "full source registry" })
      ]));
    }
  }

  /* --------------------------------------------------------- lifecycle */

  function afterChange() {
    writeParams();
    renderTypeSeg();
    renderWeeknav();
    renderResults();
    renderStatusbar();
  }

  function loadSeason(season, fresh) {
    return N.getJson("seasons/" + season + ".json", { fresh: !!fresh })
      .then(function (doc) { state.seasonDoc = doc; });
  }

  function boot() {
    readParams();
    $("q").value = state.q;
    $("statusSel").value = state.status;

    return Promise.all([
      N.getManifest().catch(function () { return null; }),
      N.getTeams().catch(function () { return {}; }),
      N.getIndex().catch(function () { return null; }),
      N.getLinkCheck()
    ]).then(function (res) {
      state.manifest = res[0];
      state.teams = res[1] || {};
      state.index = res[2];
      state.linkCheck = res[3];

      if (!state.index || !state.manifest) {
        showNoData();
        return null;
      }
      var cur = state.index.current || {};
      if (!state.season) state.season = cur.season || (seasonsAvailable()[0] || null);
      if (!state.season) { showNoData(); return null; }
      if (!state.type || typesForSeason().indexOf(state.type) === -1) {
        state.type = cur.season_type || typesForSeason()[0] || "REG";
      }
      if (state.week === null && cur.week && cur.season === state.season) state.week = cur.week;

      renderSeasonSelect();
      renderTeamSelect();
      return loadSeason(state.season).then(function () {
        renderTypeSeg();
        renderWeeknav();
        renderResults();
        renderStatusbar();
        renderNotices();
        renderFootMeta();
        wireEvents();
        startTimer();
      });
    }).catch(function (err) {
      showNoData(err);
    });
  }

  function renderFootMeta() {
    var m = state.manifest;
    if (!m) return;
    var g = m.generator || {};
    var bits = [
      "Snapshot generated " + (m.generated_at || "unknown"),
      g.version ? ("pipeline v" + g.version) : null,
      g.run_url ? N.el("a", { href: g.run_url, target: "_blank", rel: "noopener noreferrer", text: "build log" }) : null
    ].filter(Boolean);
    var p = N.clear($("footMeta"));
    bits.forEach(function (b, i) {
      if (i) p.appendChild(document.createTextNode(" \u00b7 "));
      p.appendChild(typeof b === "string" ? document.createTextNode(b) : b);
    });
  }

  function showNoData(err) {
    N.clear($("statusbar")).appendChild(
      N.el("span", { class: "pill pill--bad" }, ["Data snapshot missing"])
    );
    N.clear($("results")).appendChild(N.el("div", { class: "empty" }, [
      N.el("h3", { text: "No data snapshot has been published yet" }),
      N.el("p", { text: "This page reads generated JSON from docs/data/. That directory is " +
        "produced by the refresh-data GitHub Action. If it is empty, run the workflow " +
        "(Actions \u2192 Refresh NFL data \u2192 Run workflow) or check the latest run log." }),
      err ? N.el("p", { class: "mono", text: String(err && err.message || err) }) : null
    ]));
  }

  function refresh() {
    var btn = $("refreshBtn");
    btn.disabled = true;
    btn.textContent = "Refreshing\u2026";
    Promise.all([
      N.getJson("manifest.json", { fresh: true }).catch(function () { return state.manifest; }),
      N.getJson("seasons/index.json", { fresh: true }).catch(function () { return state.index; }),
      loadSeason(state.season, true).catch(function () { return null; })
    ]).then(function (res) {
      if (res[0]) state.manifest = res[0];
      if (res[1]) state.index = res[1];
      renderSeasonSelect();
      renderTypeSeg();
      renderWeeknav();
      renderResults();
      renderStatusbar();
      renderNotices();
      renderFootMeta();
    }).catch(function () { /* keep showing the last good snapshot */ })
      .then(function () { btn.disabled = false; btn.textContent = "Refresh now"; });
  }

  function startTimer() {
    stopTimer();
    if (!$("autoRefresh").checked) return;
    state.timer = setInterval(function () {
      // Skip the network when the tab is hidden; nobody is looking and it saves
      // requests against GitHub Pages.
      if (document.hidden) return;
      refresh();
    }, 60000);
  }

  function stopTimer() { if (state.timer) { clearInterval(state.timer); state.timer = null; } }

  function wireEvents() {
    $("seasonSel").addEventListener("change", function (e) {
      state.season = parseInt(e.target.value, 10);
      state.week = null;
      loadSeason(state.season).then(afterChange).then(renderNotices);
    });
    $("teamSel").addEventListener("change", function (e) {
      state.team = e.target.value; afterChange();
    });
    $("statusSel").addEventListener("change", function (e) {
      state.status = e.target.value; afterChange();
    });
    var debounce = null;
    $("q").addEventListener("input", function (e) {
      clearTimeout(debounce);
      var v = e.target.value;
      debounce = setTimeout(function () { state.q = v; afterChange(); }, 180);
    });
    $("refreshBtn").addEventListener("click", refresh);
    $("autoRefresh").addEventListener("change", function () {
      if ($("autoRefresh").checked) startTimer(); else stopTimer();
    });
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && $("autoRefresh").checked) refresh();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
