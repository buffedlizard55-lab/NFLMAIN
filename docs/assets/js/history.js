/* ==========================================================================
   Historical archive controller (docs/history.html)
   ========================================================================== */
(function () {
  "use strict";

  var N = window.NFL;
  var $ = function (id) { return document.getElementById(id); };

  var state = {
    manifest: null, index: null, teams: {}, linkCheck: null,
    seasonDoc: null, season: null, type: "REG", week: "", team: "", q: ""
  };

  function seasons() { return ((state.index && state.index.seasons) || []); }

  /* ------------------------------------------------------------ controls */

  function renderSeasonGrid() {
    var grid = N.clear($("seasonGrid"));
    seasons().forEach(function (s) {
      var counts = s.status_counts || {};
      var played = (counts.FINAL || 0) + (counts.IN_PROGRESS || 0);
      grid.appendChild(N.el("button", {
        type: "button", class: "season-card",
        "aria-pressed": s.season === state.season ? "true" : "false",
        onclick: function () { selectSeason(s.season); }
      }, [
        N.el("div", { class: "season-card__yr", text: String(s.season) }),
        N.el("div", { class: "season-card__n", text: s.game_count + " games" }),
        N.el("div", { class: "season-card__n", text: played + " with a result" })
      ]));
    });
  }

  function typesForSeason() {
    var s = seasons().filter(function (x) { return x.season === state.season; })[0];
    var keys = s ? Object.keys(s.season_types || {}) : ["REG"];
    if (!keys.length) keys = ["REG"];
    var order = ["PRE", "REG", "POST"];
    keys.sort(function (a, b) {
      var ia = order.indexOf(a), ib = order.indexOf(b);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });
    return keys;
  }

  function renderTypeSeg() {
    var seg = N.clear($("archTypeSeg"));
    var types = typesForSeason();
    if (types.indexOf(state.type) === -1) state.type = types.indexOf("REG") !== -1 ? "REG" : types[0];
    types.forEach(function (t) {
      seg.appendChild(N.el("button", {
        type: "button", "aria-pressed": t === state.type ? "true" : "false",
        onclick: function () { state.type = t; state.week = ""; renderTypeSeg(); renderWeekSelect(); renderResults(); }
      }, [N.seasonTypeLabel(t).replace(" season", "")]));
    });
  }

  function renderWeekSelect() {
    var sel = N.clear($("archWeek"));
    var weeks = {};
    ((state.seasonDoc && state.seasonDoc.games) || []).forEach(function (g) {
      if ((g.season_type || "") === state.type && g.week !== null && g.week !== undefined) weeks[g.week] = true;
    });
    var list = Object.keys(weeks).map(Number).sort(function (a, b) { return a - b; });
    sel.appendChild(N.el("option", { value: "", text: "All weeks" }));
    list.forEach(function (w) {
      sel.appendChild(N.el("option", {
        value: w, selected: String(w) === state.week ? true : null,
        text: state.type === "POST" ? ("Playoff wk " + w) : ("Week " + w)
      }));
    });
    sel.value = state.week;
  }

  function renderTeamSelect() {
    var sel = N.clear($("archTeam"));
    sel.appendChild(N.el("option", { value: "", text: "All teams" }));
    // Only offer teams that actually appear in this season, so the filter is never a
    // dead end (franchises have relocated and been renamed over 28 seasons).
    var present = {};
    ((state.seasonDoc && state.seasonDoc.games) || []).forEach(function (g) {
      if (g.away && g.away.abbr) present[g.away.abbr] = g.away.name || g.away.abbr;
      if (g.home && g.home.abbr) present[g.home.abbr] = g.home.name || g.home.abbr;
    });
    Object.keys(present).sort().forEach(function (a) {
      sel.appendChild(N.el("option", { value: a, text: present[a] + " (" + a + ")" }));
    });
    if (!present[state.team]) state.team = "";
    sel.value = state.team;
  }

  function selectSeason(season) {
    state.season = season;
    state.week = "";
    return N.getSeason(season).then(function (doc) {
      state.seasonDoc = doc;
      renderSeasonGrid();
      renderTypeSeg();
      renderWeekSelect();
      renderTeamSelect();
      renderStandings();
      renderResults();
      syncUrl();
    });
  }

  function syncUrl() {
    var p = new URLSearchParams();
    if (state.season) p.set("season", state.season);
    if (state.type) p.set("type", state.type);
    if (state.week) p.set("week", state.week);
    if (state.team) p.set("team", state.team);
    if (state.q) p.set("q", state.q);
    var qs = p.toString();
    window.history.replaceState(null, "", window.location.pathname + (qs ? "?" + qs : ""));
  }

  /* ------------------------------------------------------------ standings */

  /**
   * Standings derived purely from the games already published for this season.
   * Hard rules honoured here (PROJECT_PROMPT R2):
   *   * Only FINAL regular-season games with two published scores are counted.
   *   * A "final" game missing a score is NOT guessed; it is excluded and the
   *     exclusion is stated on the page.
   *   * This is a derived view. The official table is linked, never replaced.
   */
  function standingsRows() {
    var games = ((state.seasonDoc && state.seasonDoc.games) || []);
    var table = {};
    var skipped = 0;
    games.forEach(function (g) {
      if ((g.season_type || "") !== "REG") return;
      if (g.status !== "FINAL") return;
      var a = g.away || {}, h = g.home || {};
      if (!a.abbr || !h.abbr || a.score === null || a.score === undefined ||
          h.score === null || h.score === undefined) {
        skipped += 1;
        return;
      }
      function entry(card) {
        if (!table[card.abbr]) {
          table[card.abbr] = {
            abbr: card.abbr, name: card.name || card.abbr,
            card: card, gp: 0, w: 0, l: 0, t: 0, pf: 0, pa: 0
          };
        }
        return table[card.abbr];
      }
      var aw = entry(a), ho = entry(h);
      aw.gp++; ho.gp++;
      aw.pf += a.score; aw.pa += h.score;
      ho.pf += h.score; ho.pa += a.score;
      if (a.score === h.score) { aw.t++; ho.t++; }
      else if (a.score > h.score) { aw.w++; ho.l++; }
      else { ho.w++; aw.l++; }
    });
    var rows = Object.keys(table).map(function (k) {
      var r = table[k];
      r.pct = r.gp ? Math.round(((r.w + r.t / 2) / r.gp) * 1000) / 1000 : null;
      r.diff = r.pf - r.pa;
      return r;
    });
    rows.sort(function (x, y) {
      return (y.pct - x.pct) || (y.diff - x.diff) || (y.pf - x.pf) ||
        String(x.name).localeCompare(String(y.name));
    });
    return { rows: rows, skipped: skipped };
  }

  function renderStandings() {
    var section = $("standingsSection");
    if (!section) return;
    var host = $("standings");
    if (!host) return;
    N.clear(host);
    var s = standingsRows();
    if (!s.rows.length) { section.hidden = true; return; }
    section.hidden = false;

    var note = $("standingsNote");
    if (note) {
      N.clear(note);
      note.appendChild(document.createTextNode(
        "Computed only from games this archive marks Final; " + s.rows.length +
        " team" + (s.rows.length === 1 ? "" : "s") +
        ", " + s.rows.reduce(function (n, r) { return n + r.gp; }, 0) / 2 +
        " game" + (s.rows.reduce(function (n, r) { return n + r.gp; }, 0) === 2 ? "" : "s") +
        " counted. "));
      if (s.skipped) {
        note.appendChild(document.createTextNode(
          s.skipped + " Final game" + (s.skipped === 1 ? "" : "s") +
          " without published scores " + (s.skipped === 1 ? "was" : "were") +
          " excluded rather than guessed. "));
      }
      note.appendChild(document.createTextNode(
        "Order: win pct, then point differential, then points for - not the league's " +
        "tiebreakers. Official table: "));
      note.appendChild(N.el("a", {
        href: "https://www.nfl.com/standings/", target: "_blank",
        rel: "noopener noreferrer", text: "nfl.com/standings"
      }));
      note.appendChild(document.createTextNode(" Click a row to filter the results below."));
    }

    var table = N.el("table", { class: "data standings" });
    var thead = N.el("tr", {}, [
      N.el("th", { text: "#" }),
      N.el("th", { text: "Team" }),
      N.el("th", { class: "num", text: "GP" }),
      N.el("th", { class: "num", text: "W" }),
      N.el("th", { class: "num", text: "L" }),
      N.el("th", { class: "num", text: "T" }),
      N.el("th", { class: "num", text: "PCT" }),
      N.el("th", { class: "num", text: "PF" }),
      N.el("th", { class: "num", text: "PA" }),
      N.el("th", { class: "num", text: "DIFF" })
    ]);
    table.appendChild(N.el("thead", {}, [thead]));
    var tbody = N.el("tbody");
    s.rows.forEach(function (r, i) {
      var selected = state.team === r.abbr;
      var tr = N.el("tr", {
        class: "standings-row" + (selected ? " is-selected" : ""),
        onclick: function () {
          state.team = selected ? "" : r.abbr;
          renderTeamSelect();
          renderResults();
          renderStandings();
          syncUrl();
        }
      }, [
        N.el("td", { class: "rank", text: String(i + 1) }),
        N.el("td", { class: "team" }, [N.logoEl(r.card, "logo--sm"), " ", r.abbr + " ",
          N.el("span", { style: "color:var(--text-faint)", text: r.name })]),
        N.el("td", { class: "num", text: String(r.gp) }),
        N.el("td", { class: "num", text: String(r.w) }),
        N.el("td", { class: "num", text: String(r.l) }),
        N.el("td", { class: "num", text: String(r.t) }),
        N.el("td", { class: "num", text: r.pct === null ? "\u2014" : r.pct.toFixed(3) }),
        N.el("td", { class: "num", text: String(r.pf) }),
        N.el("td", { class: "num", text: String(r.pa) }),
        N.el("td", { class: "num", text: (r.diff > 0 ? "+" : "") + r.diff })
      ]);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    host.appendChild(table);
  }

  /* -------------------------------------------------------------- render */

  function filtered() {
    var q = state.q.trim().toLowerCase();
    return ((state.seasonDoc && state.seasonDoc.games) || []).filter(function (g) {
      if ((g.season_type || "") !== state.type) return false;
      if (state.week && String(g.week) !== state.week) return false;
      if (state.team) {
        var a = g.away && g.away.abbr, h = g.home && g.home.abbr;
        if (a !== state.team && h !== state.team) return false;
      }
      if (q) {
        var hay = [g.game_id, g.away && g.away.name, g.away && g.away.abbr,
          g.home && g.home.name, g.home && g.home.abbr, g.venue && g.venue.stadium,
          g.ids && g.ids.nfl_gsis_old_game_id, g.people && g.people.referee]
          .filter(Boolean).join(" ").toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
  }

  function renderResults() {
    var box = N.clear($("results"));
    var games = filtered();

    $("pageSub").textContent = state.season
      ? (games.length + " game" + (games.length === 1 ? "" : "s") + " in the " +
         state.season + " " + N.seasonTypeLabel(state.type).toLowerCase())
      : "Select a season.";

    if (!state.season) return;

    if (!games.length) {
      box.appendChild(N.el("div", { class: "empty" }, [
        N.el("h3", { text: "No games match" }),
        N.el("p", { text: "Clear a filter, or choose a different season type." })
      ]));
      return;
    }

    // Group by week so a season reads like a season, not a flat dump.
    var byWeek = {};
    var order = [];
    games.forEach(function (g) {
      var k = g.week === null || g.week === undefined ? "?" : g.week;
      if (!byWeek[k]) { byWeek[k] = []; order.push(k); }
      byWeek[k].push(g);
    });
    order.sort(function (a, b) { return (a === "?" ? 1e9 : a) - (b === "?" ? 1e9 : b); });

    order.forEach(function (w) {
      box.appendChild(N.el("h2", {
        class: "section-title",
        text: state.type === "POST" ? ("Playoff week " + w) : ("Week " + w)
      }));
      var list = N.el("div", { class: "list" });
      byWeek[w].forEach(function (g) { list.appendChild(row(g)); });
      box.appendChild(list);
    });

    var prov = state.seasonDoc && state.seasonDoc.provenance;
    if (prov) {
      box.appendChild(N.el("p", { class: "card__meta", style: "margin-top:14px" }, [
        "Provenance: ", N.el("code", { text: prov.source_id }), " \u00b7 ",
        N.el("a", { href: prov.upstream_url, target: "_blank", rel: "noopener noreferrer", text: "upstream dataset" }),
        " \u00b7 verify at ",
        N.el("a", { href: prov.official_review_url, target: "_blank", rel: "noopener noreferrer", text: "NFL.com/scores" })
      ]));
    }
  }

  function row(g) {
    var away = g.away || {}, home = g.home || {};
    var showScore = g.status !== "SCHEDULED";
    var scoreText = showScore
      ? (N.score(away.score) + " \u2013 " + N.score(home.score))
      : N.kickoff(g, true);

    var teamsCell = N.el("span", { class: "list-row__teams" }, [
      N.logoEl(away, "logo--sm"), " ",
      N.el("span", { text: away.abbr || "?" }),
      " @ ",
      N.el("span", { text: home.abbr || "?" }), " ",
      N.logoEl(home, "logo--sm"),
      N.el("span", { style: "color:var(--text-faint);font-weight:500", text: "  " + (away.name || "") + " at " + (home.name || "") })
    ]);

    var actions = N.el("span", { style: "display:flex;gap:6px;align-items:center" });
    var flags = N.irregularityFlags(g);
    if (flags) actions.appendChild(flags);
    if (showScore) actions.appendChild(N.badgeFor(g));
    var href = "game.html?id=" + encodeURIComponent(g.game_id || "") + "&season=" + state.season;
    actions.appendChild(N.el("a", { class: "linkbtn", href: href, text: g.pbp_available ? "Play-by-play" : "Details" }));
    var nfl = N.nflLink(g.links && g.links.nfl_game, "NFL.com", { primary: true, linkCheck: state.linkCheck });
    if (nfl) actions.appendChild(nfl);

    return N.el("div", { class: "list-row" }, [
      N.el("span", { class: "list-row__wk", text: g.gameday || ("wk " + N.num(g.week)) }),
      teamsCell,
      N.el("span", { class: "list-row__score", text: scoreText }),
      actions
    ]);
  }

  function renderStatusbar() {
    var bar = N.clear($("statusbar"));
    var m = state.manifest;
    if (!m) { bar.appendChild(N.el("span", { class: "pill pill--bad" }, ["No data snapshot"])); return; }
    var cov = m.coverage || {};
    bar.appendChild(N.el("span", { class: "pill pill--ok" }, ["Data as of " + N.relativeTime(m.generated_at)]));
    bar.appendChild(N.el("span", { class: "pill" }, [
      "Archive: " + (cov.season_min || "?") + "\u2013" + (cov.season_max || "?") +
      " \u00b7 " + (cov.game_count || 0).toLocaleString() + " games"
    ]));
    bar.appendChild(N.el("span", { class: "pill" }, [
      "Play-by-play built for " + (cov.pbp_games || 0).toLocaleString() + " games"
    ]));
    if (m.irregularities && m.irregularities.total) {
      bar.appendChild(N.el("a", { class: "pill pill--warn", href: "sources.html#irregularities" },
        ["\u26a0 " + m.irregularities.total + " flags"]));
    }
  }

  function boot() {
    var p = new URLSearchParams(window.location.search);
    if (p.get("season")) state.season = parseInt(p.get("season"), 10) || null;
    if (p.get("type")) state.type = p.get("type").toUpperCase();
    if (p.get("week")) state.week = p.get("week");
    if (p.get("team")) state.team = p.get("team").toUpperCase();
    if (p.get("q")) { state.q = p.get("q"); $("archQ").value = state.q; }

    Promise.all([
      N.getManifest().catch(function () { return null; }),
      N.getIndex().catch(function () { return null; }),
      N.getTeams().catch(function () { return {}; }),
      N.getLinkCheck()
    ]).then(function (res) {
      state.manifest = res[0]; state.index = res[1]; state.teams = res[2] || {}; state.linkCheck = res[3];
      if (!state.index) {
        N.clear($("results")).appendChild(N.el("div", { class: "empty" }, [
          N.el("h3", { text: "No data snapshot published yet" }),
          N.el("p", { text: "Run the refresh-data GitHub Action to build docs/data/." })
        ]));
        renderStatusbar();
        return null;
      }
      if (!state.season) state.season = (state.index.current || {}).season || seasons()[0].season;

      var earliest = state.index.earliest_pbp_season;
      if (earliest) {
        $("notices").appendChild(N.el("div", { class: "notice notice--info" }, [
          N.el("h4", { text: "How far back the archive goes" }),
          N.el("div", {}, [
            "NFL play-by-play is published upstream from the ",
            N.el("strong", { text: String(earliest) }),
            " season onward, so that is the floor of this archive. Seasons before " +
            String(earliest) + " are not included because the NFL's own play-by-play feed " +
            "does not cover them \u2014 listing them here would mean inventing data. "
          ]),
          N.el("div", { style: "margin-top:6px" }, [
            N.el("a", { href: "sources.html#coverage", text: "See coverage notes" })
          ])
        ]));
      }

      renderSeasonGrid();
      return selectSeason(state.season).then(function () {
        renderStatusbar();
        renderFoot();
      });
    }).catch(function (err) {
      N.clear($("results")).appendChild(N.el("div", { class: "empty" }, [
        N.el("h3", { text: "Could not load the archive" }),
        N.el("p", { class: "mono", text: String(err && err.message || err) })
      ]));
    });
  }

  function renderFoot() {
    var m = state.manifest;
    if (!m) return;
    var p = N.clear($("footMeta"));
    p.appendChild(document.createTextNode("Snapshot generated " + (m.generated_at || "unknown")));
    if (m.generator && m.generator.run_url) {
      p.appendChild(document.createTextNode(" \u00b7 "));
      p.appendChild(N.el("a", { href: m.generator.run_url, target: "_blank", rel: "noopener noreferrer", text: "build log" }));
    }
  }

  function wire() {
    $("archWeek").addEventListener("change", function (e) { state.week = e.target.value; renderResults(); syncUrl(); });
    $("archTeam").addEventListener("change", function (e) { state.team = e.target.value; renderResults(); syncUrl(); });
    var deb = null;
    $("archQ").addEventListener("input", function (e) {
      clearTimeout(deb);
      var v = e.target.value;
      deb = setTimeout(function () { state.q = v; renderResults(); syncUrl(); }, 180);
    });
    $("archClear").addEventListener("click", function () {
      state.week = ""; state.team = ""; state.q = ""; $("archQ").value = "";
      renderWeekSelect(); renderTeamSelect(); renderResults(); syncUrl();
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { wire(); boot(); });
  else { wire(); boot(); }
})();
