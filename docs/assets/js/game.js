/* ==========================================================================
   Game detail controller (docs/game.html?id=<game_id>&season=<season>)

   Renders the official play-by-play, drives, box score and stat leaders for one game.
   If play-by-play has not been built for this game, it says so plainly and still shows
   everything the schedule feed does contain - it never fills the gap with invented data.
   ========================================================================== */
(function () {
  "use strict";

  var N = window.NFL;
  var $ = function (id) { return document.getElementById(id); };

  var state = {
    doc: null,          // full pbp document, or null
    game: null,         // game object (from pbp doc or season doc)
    season: null,
    gameId: null,
    linkCheck: null,
    filter: "all",
    qtr: "",
    q: ""
  };

  /* ------------------------------------------------------------- filters */

  var FILTERS = [
    { id: "all", label: "All plays" },
    { id: "scoring", label: "Scoring" },
    { id: "pass", label: "Pass" },
    { id: "rush", label: "Rush" },
    { id: "penalty", label: "Penalties" },
    { id: "turnover", label: "Turnovers" },
    { id: "special", label: "Special teams" },
    { id: "action", label: "Action only" }
  ];

  function matchesFilter(p, f) {
    if (f === "all") return true;
    if (f === "action") return !!p.is_real_play;
    if (f === "scoring") return !!p.is_scoring_play;
    if (f === "pass") return !!(p.pass_attempt || p.complete_pass || p.incomplete_pass || p.interception || p.sack);
    if (f === "rush") return !!(p.rush_attempt || p.rushing_yards !== null && p.rushing_yards !== undefined);
    if (f === "penalty") return !!p.penalty;
    if (f === "turnover") return !!(p.interception || p.fumble_lost);
    if (f === "special") return !!(p.special_teams_play || p.kickoff_attempt || p.punt_attempt ||
      p.field_goal_attempt || p.extra_point_attempt || p.two_point_attempt);
    return true;
  }

  /* -------------------------------------------------------------- render */

  function playTag(p) {
    if (p.pass_touchdown || p.rush_touchdown || p.return_touchdown) {
      return N.el("span", { class: "tag tag--td", text: "TD" });
    }
    if (p.field_goal_result === "made") return N.el("span", { class: "tag tag--fg", text: "FG" });
    if (p.interception) return N.el("span", { class: "tag tag--to", text: "INT" });
    if (p.fumble_lost) return N.el("span", { class: "tag tag--to", text: "FUM" });
    if (p.penalty) return N.el("span", { class: "tag tag--pen", text: "PEN" });
    if (p.safety) return N.el("span", { class: "tag tag--td", text: "SAFETY" });
    return null;
  }

  function renderHeader(g) {
    var away = g.away || {}, home = g.home || {};
    var showScore = g.status !== "SCHEDULED";

    var mid = N.el("div", { class: "matchup__mid" }, [
      N.badgeFor(g),
      N.el("div", { style: "margin-top:6px", text: N.kickoff(g, true) }),
      N.el("div", { class: "matchup__record" }, [
        (g.season_type === "POST" ? "Playoff wk " : "Week ") + N.num(g.week) +
        " \u00b7 " + N.num(g.season) + " \u00b7 " + N.seasonTypeLabel(g.season_type)
      ])
    ]);

    function side(team, isAway) {
      var winner = null;
      if (showScore && away.score !== null && home.score !== null) {
        winner = isAway ? away.score > home.score : home.score > away.score;
      }
      var s = N.el("div", {
        class: "matchup__side " + (isAway ? "matchup__side--away" : "matchup__side--home")
      });
      s.appendChild(N.el("div", { class: "row" }, [
        N.logoEl(team, "logo--lg"),
        N.el("div", {}, [
          N.el("div", { class: "matchup__name", text: team.name || team.abbr || N.DASH }),
          N.el("div", { class: "matchup__record", text: (team.abbr || "") + (isAway ? " \u00b7 away" : " \u00b7 home") })
        ])
      ]));
      s.appendChild(N.el("div", {
        class: "matchup__score",
        style: winner === false ? "color:var(--text-dim)" : null,
        text: showScore ? N.score(team.score) : ""
      }));
      if (winner === true) {
        s.appendChild(N.el("div", { class: "badge badge--final", text: "Winner" }));
      }
      if (team.name && team.abbr) {
        var teamUrl = isAway ? (g.links || {}).nfl_team_away : (g.links || {}).nfl_team_home;
        if (teamUrl && !(state.linkCheck && N.linkIsBroken(state.linkCheck, teamUrl))) {
          s.appendChild(N.el("a", {
            class: "linkbtn", href: teamUrl, target: "_blank", rel: "noopener noreferrer external",
            text: "Official club page"
          }));
        }
      }
      return s;
    }

    var head = N.el("div", { class: "gamehead" }, [
      N.el("div", { class: "matchup" }, [side(away, true), mid, side(home, false)])
    ]);

    var qs = g.quarter_scores;
    if (qs && qs.labels && qs.labels.length) {
      var rows = [
        N.el("tr", {}, [N.el("th", { text: "Team" })].concat(
          qs.labels.map(function (l) { return N.el("th", { text: l }); })
        ).concat([N.el("th", { text: "Total" })]))
      ];
      [[away, qs.away, qs.away_total], [home, qs.home, qs.home_total]].forEach(function (r) {
        rows.push(N.el("tr", {}, [
          N.el("td", {}, [N.logoEl(r[0], "logo--sm"), " ", N.el("span", { text: r[0].abbr || "" })])
        ].concat(r[1].map(function (v) { return N.el("td", { class: "num", text: N.num(v) }); }))
         .concat([N.el("td", { class: "num", style: "font-weight:800", text: N.num(r[2]) })])));
      });
      head.appendChild(N.el("div", { class: "qline", style: "margin-top:12px" }, [
        N.el("table", {}, [N.el("thead", {}, [rows[0]]), N.el("tbody", {}, rows.slice(1))])
      ]));
    }
    return head;
  }

  function infoPanel(g) {
    var v = g.venue || {}, p = g.people || {}, ids = g.ids || {};
    function kv(label, value) {
      return [N.el("dt", { text: label }), N.el("dd", { text: N.text(value) })];
    }
    var dl = N.el("dl", { class: "kv" });
    [
      ["Stadium", v.stadium],
      ["Location", v.location],
      ["Roof", v.roof],
      ["Surface", v.surface],
      ["Temperature", v.temp_f === null || v.temp_f === undefined ? null : (v.temp_f + " \u00b0F")],
      ["Wind", v.wind_mph === null || v.wind_mph === undefined ? null : (v.wind_mph + " mph")],
      ["Referee", p.referee],
      ["Away coach", p.away_coach],
      ["Home coach", p.home_coach],
      ["Divisional game", g.division_game === true ? "Yes" : (g.division_game === false ? "No" : null)]
    ].forEach(function (pair) {
      kv(pair[0], pair[1]).forEach(function (n) { dl.appendChild(n); });
    });

    var idsDl = N.el("dl", { class: "kv" });
    [
      ["NFL GSIS game id", ids.nfl_gsis_old_game_id],
      ["NFL API game UUID", ids.nfl_api_id],
      ["NFL GSIS sequence", ids.nfl_gsis],
      ["Stadium id", v.stadium_id],
      ["PFR id", ids.pfr],
      ["ESPN id", ids.espn],
      ["This project's id", ids.nflverse_game_id]
    ].forEach(function (pair) {
      kv(pair[0], pair[1]).forEach(function (n) { idsDl.appendChild(n); });
    });

    var links = g.links || {};
    var linkBox = N.el("div", { style: "display:flex;flex-wrap:wrap;gap:6px;margin-top:8px" });
    [
      [links.nfl_game, "NFL.com Game Center", true],
      // The league's own game summary document, served unauthenticated at a
      // version-less URL that was verified on 2026-09-25. It is the strongest
      // "check this yourself" affordance on the page: scoring plays, drive charts and
      // final individual statistics, straight from the NFL. Only rendered when the
      // NFL API game UUID is known, because the PDF is keyed by that UUID.
      [links.nfl_gamebook, "Official Game Book (PDF)", true],
      [links.nfl_week, "NFL.com week page", false],
      [links.nfl_scores, "NFL.com scoreboard", false],
      [links.nfl_standings, "NFL.com standings", false],
      [links.nfl_team_away, "Away club page", false],
      [links.nfl_team_home, "Home club page", false]
    ].forEach(function (l) {
      var node = N.nflLink(l[0], l[1], { primary: l[2], linkCheck: state.linkCheck });
      if (node) linkBox.appendChild(node);
    });

    return N.el("div", { class: "panels" }, [
      N.el("section", { class: "panel" }, [N.el("h3", { text: "Game info" }), dl]),
      N.el("section", { class: "panel" }, [
        N.el("h3", { text: "Official identifiers & links" }),
        idsDl,
        N.el("p", { class: "card__meta", style: "margin:10px 0 0" }, [
          "These are the NFL's own identifiers for this game. Use the Game Center link, or " +
          "the Game Book PDF the league publishes for it" +
          (links.nfl_gamebook ? "" : " (not linked here: the NFL API game UUID is not " +
            "published upstream for this game, so the PDF's address cannot be built)") +
          ", to compare any figure on this page against the official NFL record."
        ]),
        linkBox
      ])
    ]);
  }

  function boxPanel(g) {
    var pbp = g.pbp;
    if (!pbp || !pbp.box_score) return null;
    var box = pbp.box_score;
    var totals = box.team_totals || {};
    var keys = Object.keys(totals);
    if (keys.length < 2) return null;
    var home = g.home && g.home.abbr, away = g.away && g.away.abbr;
    var order = [away, home].filter(function (k) { return totals[k]; });
    if (order.length < 2) order = keys.slice(0, 2);

    var rows = [
      ["Passing", "pass_comp", "pass_att", "pass_yds", "pass_td", "pass_int"],
      ["Rushing", "rush_att", "rush_yds", "rush_td"]
    ];

    var stats = [
      { label: "Pass comp/att", get: function (t) { return t.pass_comp + "/" + t.pass_att; } },
      { label: "Passing yards", get: function (t) { return t.pass_yds; } },
      { label: "Passing TD", get: function (t) { return t.pass_td; } },
      { label: "Interceptions", get: function (t) { return t.pass_int; } },
      { label: "Rush attempts", get: function (t) { return t.rush_att; } },
      { label: "Rushing yards", get: function (t) { return t.rush_yds; } },
      { label: "Rushing TD", get: function (t) { return t.rush_td; } },
      { label: "Sacks allowed", get: function (t) { return t.sacks_allowed; } },
      { label: "First downs", get: function (t) { return t.first_downs; } },
      { label: "3rd down", get: function (t) { return t.third_down_conv + "/" + t.third_down_att + " (" + N.pct(t.third_down_conv, t.third_down_att) + ")"; } },
      { label: "4th down", get: function (t) { return t.fourth_down_conv + "/" + t.fourth_down_att + " (" + N.pct(t.fourth_down_conv, t.fourth_down_att) + ")"; } },
      { label: "Penalties", get: function (t) { return t.penalties + " for " + t.penalty_yds + " yds"; } },
      { label: "Turnovers", get: function (t) { return t.turnovers; } }
    ];

    var head = N.el("tr", {}, [
      N.el("th", { text: "Team stat" })
    ].concat(order.map(function (k) {
      return N.el("th", { class: "num", text: k });
    })));

    var body = stats.map(function (s) {
      return N.el("tr", {}, [N.el("td", { text: s.label })].concat(
        order.map(function (k) {
          var v = s.get(totals[k] || {});
          return N.el("td", { class: "num", text: (v === null || v === undefined) ? N.DASH : String(v) });
        })
      ));
    });

    var panel = N.el("section", { class: "panel" }, [
      N.el("h3", { text: "Team statistics (aggregated from the official plays)" }),
      N.el("table", { class: "data" }, [N.el("thead", {}, [head]), N.el("tbody", {}, body)]),
      N.el("p", { class: "card__meta", style: "margin-top:8px" }, [
        "Computed by summing the per-play values published in the NFL play-by-play feed. " +
        "Compare against the official box score on the NFL.com Game Center page linked above."
      ])
    ]);

    var leaders = N.el("section", { class: "panel" }, [N.el("h3", { text: "Stat leaders" })]);
    [
      ["Passing", box.passing_leaders, function (r) {
        return (r.name || N.DASH) + " \u2014 " + (r.comp || 0) + "/" + (r.att || 0) +
          ", " + (r.yds || 0) + " yds, " + (r.td || 0) + " TD, " + (r.int || 0) + " INT";
      }],
      ["Rushing", box.rushing_leaders, function (r) {
        return (r.name || N.DASH) + " \u2014 " + (r.att || 0) + " car, " + (r.yds || 0) +
          " yds, " + (r.td || 0) + " TD";
      }],
      ["Receiving", box.receiving_leaders, function (r) {
        return (r.name || N.DASH) + " \u2014 " + (r.rec || 0) + " rec, " + (r.yds || 0) +
          " yds, " + (r.td || 0) + " TD";
      }],
      ["Defense", box.defense_leaders, function (r) {
        var bits = [];
        if (r.sacks) bits.push(r.sacks + " sack" + (r.sacks === 1 ? "" : "s"));
        if (r.ints) bits.push(r.ints + " INT");
        return (r.name || N.DASH) + " \u2014 " + (bits.join(", ") || N.DASH);
      }]
    ].forEach(function (group) {
      var list = group[1] || [];
      leaders.appendChild(N.el("div", { class: "section-title", style: "margin:12px 0 4px", text: group[0] }));
      if (!list.length) {
        leaders.appendChild(N.el("div", { class: "card__meta", text: "No plays of this type upstream." }));
        return;
      }
      var ul = N.el("ul", { style: "margin:0;padding-left:18px;font-size:13px" });
      list.forEach(function (r) { ul.appendChild(N.el("li", { text: group[2](r) })); });
      leaders.appendChild(ul);
    });

    return N.el("div", { class: "panels", style: "margin-top:12px" }, [panel, leaders]);
  }

  function drivesPanel(g) {
    var pbp = g.pbp;
    if (!pbp || !pbp.drives || !pbp.drives.length) return null;
    var head = N.el("tr", {}, ["#", "Team", "Qtr", "Start", "Plays", "Result", "Score after"]
      .map(function (h, i) {
        return N.el("th", { class: i >= 4 && i <= 4 ? "num" : null, text: h });
      }));
    var body = pbp.drives.map(function (d) {
      var after = (d.end_score && d.end_score.length === 2)
        ? ((g.away && g.away.abbr) + " " + N.num(d.end_score[0]) + " \u2013 " +
           N.num(d.end_score[1]) + " " + ((g.home && g.home.abbr) || ""))
        : N.DASH;
      return N.el("tr", {}, [
        N.el("td", { class: "num", text: N.num(d.drive_number) }),
        N.el("td", { text: N.text(d.posteam) }),
        N.el("td", { class: "num", text: N.num(d.quarter_start) }),
        N.el("td", { text: N.text(d.start_yard_line) }),
        N.el("td", { class: "num", text: N.num(d.plays) }),
        N.el("td", { text: N.text(d.result || d.end_transition) }),
        N.el("td", { class: "pbp-clock", text: after })
      ]);
    });
    return N.el("section", { class: "panel", style: "margin-top:12px" }, [
      N.el("h3", { text: "Drives" }),
      N.el("div", { style: "overflow:auto" }, [
        N.el("table", { class: "data" }, [N.el("thead", {}, [head]), N.el("tbody", {}, body)])
      ])
    ]);
  }

  function pbpControls(g) {
    var box = N.el("section", { class: "controls", "aria-label": "Play-by-play filters" });

    var seg = N.el("div", { class: "seg", id: "pbpSeg", role: "group", "aria-label": "Play type" });
    FILTERS.forEach(function (f) {
      seg.appendChild(N.el("button", {
        type: "button", "aria-pressed": f.id === state.filter ? "true" : "false",
        onclick: function () { state.filter = f.id; renderPbp(); }
      }, [f.label]));
    });
    box.appendChild(N.el("div", { class: "field" }, [N.el("label", { text: "Filter" }), seg]));

    var quarters = {};
    (g.pbp.plays || []).forEach(function (p) { if (p.qtr !== null && p.qtr !== undefined) quarters[p.qtr] = true; });
    var qsel = N.el("select", { id: "qtrSel", onchange: function (e) { state.qtr = e.target.value; renderPbp(); } });
    qsel.appendChild(N.el("option", { value: "", text: "All quarters" }));
    Object.keys(quarters).map(Number).sort(function (a, b) { return a - b; }).forEach(function (q) {
      qsel.appendChild(N.el("option", {
        value: q, selected: String(q) === state.qtr ? true : null,
        text: q <= 4 ? ("Q" + q) : (q === 5 ? "OT" : "OT" + (q - 4))
      }));
    });
    box.appendChild(N.el("div", { class: "field" }, [N.el("label", { for: "qtrSel", text: "Quarter" }), qsel]));

    var qi = N.el("input", {
      type: "search", id: "pbpQ", placeholder: "Search play descriptions\u2026",
      value: state.q, autocomplete: "off"
    });
    var deb = null;
    qi.addEventListener("input", function (e) {
      clearTimeout(deb);
      var v = e.target.value;
      deb = setTimeout(function () { state.q = v; renderPbp(); }, 160);
    });
    box.appendChild(N.el("div", { class: "field" }, [N.el("label", { for: "pbpQ", text: "Search" }), qi]));

    return box;
  }

  function renderPbp() {
    var g = state.game;
    var host = $("pbpHost");
    if (!host || !g || !g.pbp) return;
    N.clear(host);

    var seg = $("pbpSeg");
    if (seg) {
      Array.prototype.forEach.call(seg.children, function (b, i) {
        b.setAttribute("aria-pressed", FILTERS[i].id === state.filter ? "true" : "false");
      });
    }

    var q = state.q.trim().toLowerCase();
    var plays = (g.pbp.plays || []).filter(function (p) {
      if (!matchesFilter(p, state.filter)) return false;
      if (state.qtr && String(p.qtr) !== state.qtr) return false;
      if (q) {
        var hay = [p.desc, p.play_type, p.play_type_nfl, p.posteam, p.defteam,
          p.passer_player_name, p.receiver_player_name, p.rusher_player_name,
          p.penalty_type, p.penalty_player_name].filter(Boolean).join(" ").toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });

    var meta = N.el("p", { class: "card__meta" }, [
      plays.length + " of " + (g.pbp.plays || []).length + " plays shown" +
      " \u00b7 " + N.num(g.pbp.real_play_count) + " action plays" +
      " \u00b7 " + N.num(g.pbp.scoring_play_count) + " scoring plays"
    ]);
    host.appendChild(meta);

    if (!plays.length) {
      host.appendChild(N.el("div", { class: "empty" }, [
        N.el("h3", { text: "No plays match this filter" }),
        N.el("p", { text: "Widen the filter or clear the search." })
      ]));
      return;
    }

    var head = N.el("tr", {}, [
      N.el("th", { class: "num", text: "#" }),
      N.el("th", { text: "Qtr" }),
      N.el("th", { text: "Clock" }),
      N.el("th", { text: "Down" }),
      N.el("th", { text: "Ball on" }),
      N.el("th", { text: "Score A/H" }),
      N.el("th", { text: "Play" })
    ]);

    var rows = plays.map(function (p) {
      var down = (p.down === null || p.down === undefined) ? "\u2014"
        : (p.down + (p.goal_to_go ? "&G" : "&" + N.num(p.ydstogo)));
      var sc = N.num(p.total_away_score) + " \u2013 " + N.num(p.total_home_score);
      var descCell = N.el("td", { class: "pbp-desc" }, [
        N.el("span", { text: p.desc || N.DASH }),
        playTag(p),
        (p.play_type_nfl ? N.el("span", { class: "tag", text: p.play_type_nfl }) : null),
        (p.yards_gained !== null && p.yards_gained !== undefined
          ? N.el("span", { class: "tag", text: (p.yards_gained > 0 ? "+" : "") + p.yards_gained + " yds" })
          : null)
      ].filter(Boolean));

      return N.el("tr", { class: p.is_scoring_play ? "is-score" : null }, [
        N.el("td", { class: "num pbp-clock", text: N.num(p.play_id) }),
        N.el("td", { class: "num", text: N.num(p.qtr) }),
        N.el("td", { class: "pbp-clock", text: N.text(p.time) }),
        N.el("td", { text: down }),
        N.el("td", { text: N.text(p.yrdln) }),
        N.el("td", { class: "pbp-clock", text: sc }),
        descCell
      ]);
    });

    host.appendChild(N.el("div", { class: "pbp-scroll" }, [
      N.el("table", { class: "data" }, [N.el("thead", {}, [head]), N.el("tbody", {}, rows)])
    ]));

    var prov = (g.pbp || {}).provenance;
    if (prov) {
      host.appendChild(N.el("p", { class: "card__meta", style: "margin-top:10px" }, [
        "Play-by-play provenance: ",
        N.el("code", { text: prov.source_id }),
        " \u00b7 ",
        N.el("a", { href: prov.upstream_url, target: "_blank", rel: "noopener noreferrer", text: "upstream dataset" }),
        " \u00b7 " + N.num(prov.columns_observed) + " upstream columns read",
        " \u00b7 verify at ",
        N.el("a", { href: prov.official_review_url, target: "_blank", rel: "noopener noreferrer", text: "NFL.com" })
      ]));
    }
  }

  function render(doc, fromPbp) {
    state.game = doc;
    var host = N.clear($("game"));

    document.title = ((doc.away && doc.away.name) || "?") + " at " +
      ((doc.home && doc.home.name) || "?") + " \u2014 NFL Scoreboard";

    var irr = doc.irregularities || [];
    if (irr.length) {
      $("notices").appendChild(N.el("div", { class: "notice notice--warn" }, [
        N.el("h4", { text: "Flagged for review" }),
        N.el("ul", {}, irr.map(function (i) { return N.el("li", { class: "mono", text: i }); })),
        N.el("div", {}, [
          "The pipeline detected these inconsistencies in the upstream data. They are " +
          "reported rather than silently corrected. Check the official ",
          N.el("a", {
            href: (doc.links || {}).nfl_game || "https://www.nfl.com/scores/",
            target: "_blank", rel: "noopener noreferrer", text: "NFL.com Game Center page"
          }), "."
        ])
      ]));
    }

    if (!fromPbp) {
      $("notices").appendChild(N.el("div", { class: "notice notice--info" }, [
        N.el("h4", { text: "Play-by-play not built for this game yet" }),
        N.el("div", {}, [
          "The schedule record below is real and complete, but this project has not yet " +
          "generated the play-by-play file for this game. Historical play-by-play is built " +
          "on demand to keep the published site small and fast. To add it, run the " +
          "GitHub Action ",
          N.el("code", { text: "Backfill play-by-play" }),
          " with this season, or ",
          N.el("code", { text: "Refresh NFL data" }),
          " with the season listed in ",
          N.el("code", { text: "--pbp-seasons" }), ". Nothing is invented in the meantime."
        ])
      ]));
    }

    host.appendChild(renderHeader(doc));
    host.appendChild(infoPanel(doc));

    if (doc.pbp) {
      var bx = boxPanel(doc);
      if (bx) host.appendChild(bx);
      var dp = drivesPanel(doc);
      if (dp) host.appendChild(dp);
      host.appendChild(N.el("h2", { class: "section-title", text: "Play-by-play" }));
      host.appendChild(pbpControls(doc));
      host.appendChild(N.el("div", { id: "pbpHost" }));
      renderPbp();
    }

    renderStatusbar(doc);
    renderFoot(doc);
  }

  function renderStatusbar(g) {
    var bar = N.clear($("statusbar"));
    bar.appendChild(N.badgeFor(g));
    bar.appendChild(N.el("span", { class: "pill" }, [
      g.pbp ? ((g.pbp.play_count || 0) + " plays") : "no play-by-play file"
    ]));
    if (g.pbp && g.pbp.game_end_marker_seen) {
      bar.appendChild(N.el("span", { class: "pill pill--ok" }, ["Official GAME_END play present"]));
    }
    if (g.status_estimated) {
      bar.appendChild(N.el("span", { class: "pill pill--warn", title: g.status_detail || "" },
        ["Status estimated from the kickoff clock"]));
    }
  }

  function renderFoot(g) {
    var m = state.manifest;
    var p = N.clear($("footMeta"));
    var bits = [];
    if (g && g.provenance) bits.push("Record source: " + g.provenance.source_id);
    if (m) bits.push("Snapshot generated " + m.generated_at);
    if (m && m.generator && m.generator.run_url) {
      bits.push(N.el("a", { href: m.generator.run_url, target: "_blank", rel: "noopener noreferrer", text: "build log" }));
    }
    bits.forEach(function (b, i) {
      if (i) p.appendChild(document.createTextNode(" \u00b7 "));
      p.appendChild(typeof b === "string" ? document.createTextNode(b) : b);
    });
  }

  function findInSeason(season, gameId) {
    return N.getSeason(season).then(function (doc) {
      var games = doc.games || [];
      for (var i = 0; i < games.length; i++) if (games[i].game_id === gameId) return games[i];
      return null;
    });
  }

  function boot() {
    var p = new URLSearchParams(window.location.search);
    state.gameId = p.get("id");
    state.season = p.get("season") ? parseInt(p.get("season"), 10) : null;

    if (!state.gameId) {
      N.clear($("game")).appendChild(N.el("div", { class: "empty" }, [
        N.el("h3", { text: "No game selected" }),
        N.el("p", {}, [
          "Pick a game from the ",
          N.el("a", { href: "index.html", text: "scoreboard" }),
          " or the ",
          N.el("a", { href: "history.html", text: "archive" }), "."
        ])
      ]));
      return;
    }
    if (!state.season && /^\d{4}_/.test(state.gameId)) {
      state.season = parseInt(state.gameId.slice(0, 4), 10);
    }

    Promise.all([
      N.getManifest().catch(function () { return null; }),
      N.getLinkCheck()
    ]).then(function (res) {
      state.manifest = res[0];
      state.linkCheck = res[1];
      return N.getGame(state.gameId);
    }).then(function (doc) {
      render(doc, true);
    }).catch(function () {
      // No play-by-play file: fall back to the schedule record and say so honestly.
      if (!state.season) {
        N.clear($("game")).appendChild(N.el("div", { class: "empty" }, [
          N.el("h3", { text: "Game not found" }),
          N.el("p", { text: "No play-by-play file and no season was given to look the game up in." })
        ]));
        return;
      }
      return findInSeason(state.season, state.gameId).then(function (g) {
        if (!g) {
          N.clear($("game")).appendChild(N.el("div", { class: "empty" }, [
            N.el("h3", { text: "Game not found" }),
            N.el("p", { text: "No record with id " + state.gameId + " in season " + state.season + "." })
          ]));
          return;
        }
        render(g, false);
      });
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
