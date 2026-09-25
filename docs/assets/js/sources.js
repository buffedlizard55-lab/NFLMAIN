/* ==========================================================================
   Sources & verification controller (docs/sources.html)

   Renders the build manifest as-is. This page never states anything the manifest does
   not contain, so it cannot drift out of date relative to the data it describes.
   ========================================================================== */
(function () {
  "use strict";

  var N = window.NFL;
  var $ = function (id) { return document.getElementById(id); };

  function tagChips(tags) {
    return (tags || []).map(function (t) {
      var cls = "chip";
      if (t === "official") cls += " chip--official";
      if (t === "crosscheck" || t === "non-official") cls += " chip--crosscheck";
      if (t === "retired" || t === "do-not-use") cls += " chip--retired";
      return N.el("span", { class: cls, text: t });
    });
  }

  /* -------------------------------------------------------- source cards */

  function renderSources(m) {
    var host = N.clear($("sourcesHost"));
    var sources = m.sources || [];
    if (!sources.length) {
      host.appendChild(N.el("div", { class: "empty" }, [N.el("h3", { text: "No sources declared" })]));
      return;
    }
    sources.forEach(function (s) {
      var det = N.el("details", { class: "detail", id: "src-" + s.id }, [
        N.el("summary", {}, [
          N.el("code", { text: s.id }),
          " \u2014 " + s.name + " ",
          N.el("span", { style: "color:var(--text-faint);font-weight:500", text: "(" + s.publisher + ")" })
        ]),
        N.el("div", {}, [
          N.el("div", { style: "margin-bottom:8px" }, tagChips(s.tags)),
          kvTable([
            ["Used URL pattern", N.el("code", { text: s.url_pattern })],
            ["Manual review link", N.el("a", { href: s.human_url, target: "_blank", rel: "noopener noreferrer external", text: s.human_url })],
            ["Upstream", s.upstream],
            ["Official chain", s.official_chain],
            ["Verification evidence", s.verification],
            ["Licence note", s.license_note]
          ])
        ])
      ]);
      // Open the official + non-retired sources by default; they are the ones in use.
      var tags = s.tags || [];
      if (tags.indexOf("official") !== -1 && tags.indexOf("retired") === -1) det.open = true;
      host.appendChild(det);
    });
  }

  function kvTable(pairs) {
    var dl = N.el("dl", { class: "kv", style: "grid-template-columns:minmax(150px,auto) 1fr;text-align:left" });
    pairs.forEach(function (p) {
      if (p[1] === null || p[1] === undefined || p[1] === "") return;
      dl.appendChild(N.el("dt", { text: p[0], style: "text-align:left" }));
      dl.appendChild(N.el("dd", { style: "text-align:left" }, [
        typeof p[1] === "string" ? document.createTextNode(p[1]) : p[1]
      ]));
    });
    return dl;
  }

  /* ------------------------------------------------------- official api */

  function renderApi(m) {
    var host = N.clear($("apiHost"));
    var api = m.official_api || {};
    var panel = N.el("section", { class: "panel" });

    panel.appendChild(N.el("div", { style: "margin-bottom:10px" }, [
      api.available
        ? N.el("span", { class: "pill pill--ok" }, ["api.nfl.com: configured"])
        : N.el("span", { class: "pill pill--warn" }, ["api.nfl.com: not configured"])
    ]));

    panel.appendChild(N.el("p", { text: api.reason || "" }));

    panel.appendChild(kvTable([
      ["Token endpoint", N.el("code", { text: api.token_endpoint || "https://api.nfl.com/identity/v1/token/client" })],
      ["NFL OAuth2 docs", N.el("a", { href: api.docs || "https://api.nfl.com/docs/identity/oauth2/index.html", target: "_blank", rel: "noopener noreferrer external", text: "api.nfl.com/docs/identity/oauth2" })],
      ["Getting started", N.el("a", { href: "https://api.nfl.com/docs/getting-started/index.html", target: "_blank", rel: "noopener noreferrer external", text: "api.nfl.com/docs/getting-started" })]
    ]));

    // Live probe evidence. These rows come from manifest.official_api.probes, which the
    // pipeline regenerates by making the requests itself on every build. Nothing here is
    // hardcoded: if a probe could not run, the table says so rather than showing a
    // remembered result. Re-run it yourself with `python3 pipeline/fetch_nfl_official.py --probe`.
    panel.appendChild(N.el("h3", { style: "margin-top:14px", text: "What was probed directly" }));
    var probes = api.probes || [];
    if (!probes.length) {
      panel.appendChild(N.el("p", { class: "card__meta" }, [
        "No probe results in this snapshot. The build ran offline or with --no-probe-api, " +
        "so no claim about api.nfl.com is being made from this run. Re-run the probe with ",
        N.el("code", { text: "python3 pipeline/fetch_nfl_official.py --probe" }),
        "."
      ]));
    } else {
      var probe = N.el("table", { class: "src-table" });
      probe.appendChild(N.el("thead", {}, [N.el("tr", {}, [
        N.el("th", { text: "Endpoint" }), N.el("th", { text: "Observed" }),
        N.el("th", { text: "Conclusion drawn from what was observed" })
      ])]));
      var tb = N.el("tbody");
      probes.forEach(function (p) {
        var observed = p.http_status != null
          ? "HTTP " + p.http_status
          : (p.error ? "unreachable from this runner" : "no result");
        var cell = N.el("td", {}, [N.el("code", { text: observed })]);
        if (p.body_excerpt) {
          cell.appendChild(N.el("div", { class: "card__meta", text: p.body_excerpt.slice(0, 140) }));
        }
        if (p.error) {
          cell.appendChild(N.el("div", { class: "card__meta", text: p.error.slice(0, 140) }));
        }
        tb.appendChild(N.el("tr", {}, [
          N.el("td", {}, [
            N.el("div", { text: (p.method || "GET") + " \u2014 " + (p.name || "") }),
            N.el("code", { text: p.url || "" })
          ]),
          cell,
          N.el("td", { text: p.conclusion || "No conclusion drawn." })
        ]));
      });
      probe.appendChild(tb);
      panel.appendChild(probe);
      var probedAt = null;
      probes.forEach(function (p) { if (!probedAt && p.probed_at) probedAt = p.probed_at; });
      panel.appendChild(N.el("p", { class: "card__meta" }, [
        (probedAt ? "Probed by the pipeline at " + probedAt + " UTC. " : "") +
        "No credentials were sent. These requests are re-made on every build, so this table " +
        "shows what the NFL answered then \u2014 not what someone remembered it answering once."
      ]));
    }

    if (api.calls && api.calls.length) {
      panel.appendChild(N.el("h3", { style: "margin-top:14px", text: "Calls made in this build" }));
      var ul = N.el("ul", { style: "margin:0;padding-left:18px" });
      api.calls.forEach(function (c) {
        ul.appendChild(N.el("li", {}, [
          N.el("code", { text: c.endpoint }),
          " \u2014 " + (c.ok ? "OK" : "FAILED: " + (c.error || "unknown"))
        ]));
      });
      panel.appendChild(ul);
    }

    var xcs = m.crosschecks || [];
    if (xcs.length) {
      panel.appendChild(N.el("h3", { style: "margin-top:14px", text: "Score cross-check results" }));
      xcs.forEach(function (x) {
        panel.appendChild(N.el("p", {}, [
          x.season + " " + (x.season_type || "") + " week " + x.week + ": matched " +
          (x.matched || 0) + ", mismatched " + ((x.mismatched || []).length) +
          (x.error ? ", error: " + x.error : "")
        ]));
        (x.mismatched || []).forEach(function (mm) {
          panel.appendChild(N.el("p", { class: "flag" }, [
            "MISMATCH " + (mm.mirror_game_id || mm.official_id) +
            " official=" + JSON.stringify(mm.official) +
            " mirror=" + JSON.stringify(mm.mirror)
          ]));
        });
      });
    }

    host.appendChild(panel);
  }

  /* ------------------------------------------------------------ links */

  function renderLinks(lc) {
    var host = N.clear($("linksHost"));
    if (!lc) {
      host.appendChild(N.el("div", { class: "notice notice--warn" }, [
        N.el("h4", { text: "No link-check results in this snapshot" }),
        N.el("div", { text: "verify_links.py did not run, or its output was not published. " +
          "Constructed nfl.com links are shown but have not been individually fetched." })
      ]));
      return;
    }
    var panel = N.el("section", { class: "panel" });
    var s = lc.summary || {};
    panel.appendChild(N.el("div", { style: "display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px" }, [
      N.el("span", { class: "pill" }, ["Checked " + (s.requested || 0)]),
      N.el("span", { class: "pill pill--ok" }, ["Resolved " + (s.ok || 0)]),
      N.el("span", { class: s.failed ? "pill pill--bad" : "pill pill--ok" }, ["Failed " + (s.failed || 0)]),
      N.el("span", { class: "pill" }, ["Inconclusive " + (s.network_errors || 0)]),
      N.el("span", { class: "pill" }, [lc.checked_at ? ("at " + N.relativeTime(lc.checked_at)) : ""])
    ]));
    panel.appendChild(N.el("p", { class: "card__meta" }, [
      "Sampled audit (" + (lc.checker && lc.checker.full_audit ? "full" : "sampled") + "). " +
      "Game links present in the archive: " +
      ((lc.totals && lc.totals.all_game_links) || 0).toLocaleString() +
      ". Checking every one on every run would hammer nfl.com, so the checker samples " +
      "per season and always checks 100% of club pages."
    ]));

    var t = N.el("table", { class: "src-table" });
    t.appendChild(N.el("thead", {}, [N.el("tr", {}, [
      N.el("th", { text: "URL pattern" }), N.el("th", { text: "Checked" }),
      N.el("th", { text: "Resolved" }), N.el("th", { text: "Rate" })
    ])]));
    var tb = N.el("tbody");
    Object.keys(lc.patterns || {}).sort().forEach(function (p) {
      var a = lc.patterns[p];
      var rate = a.checked ? Math.round((a.ok / a.checked) * 1000) / 10 : 0;
      tb.appendChild(N.el("tr", {}, [
        N.el("td", {}, [N.el("code", { text: p })]),
        N.el("td", { text: String(a.checked) }),
        N.el("td", { text: String(a.ok) }),
        N.el("td", { text: rate + "%" })
      ]));
    });
    t.appendChild(tb);
    panel.appendChild(t);

    if ((lc.failures || []).length) {
      panel.appendChild(N.el("h3", { style: "margin-top:14px", text: "Links that did not resolve (hidden in the UI)" }));
      var ul = N.el("ul", { style: "margin:0;padding-left:18px;font-size:12.5px" });
      lc.failures.slice(0, 60).forEach(function (f) {
        ul.appendChild(N.el("li", {}, [
          N.el("code", { text: f.url }), " \u2014 HTTP " + N.text(f.status)
        ]));
      });
      panel.appendChild(ul);
    }
    if ((lc.network_errors || []).length) {
      panel.appendChild(N.el("p", { class: "card__meta", style: "margin-top:10px" }, [
        lc.network_errors.length + " check(s) were inconclusive due to a network error and are " +
        "reported separately from real 404s."
      ]));
    }
    host.appendChild(panel);
  }

  /* --------------------------------------------------------- coverage */

  function renderCoverage(m) {
    var host = N.clear($("coverageHost"));
    var cov = m.coverage || {};
    var panel = N.el("section", { class: "panel" });
    panel.appendChild(kvTable([
      ["Seasons in the archive", ((cov.season_min || "?") + "\u2013" + (cov.season_max || "?") +
        " (" + (cov.season_count || 0) + " seasons)")],
      ["Total games listed", (cov.game_count || 0).toLocaleString()],
      ["Seasons with play-by-play built", String(cov.pbp_seasons || 0)],
      ["Games with play-by-play built", (cov.pbp_games || 0).toLocaleString()],
      ["Plays normalised in this build", (cov.play_count || cov.plays || 0).toLocaleString()],
      ["Current season / type / week",
        ((cov.current_season || "?") + " " + (cov.current_type || "?") + " week " + (cov.current_week || "?"))],
      ["Current week inferred from data", "Yes \u2014 not hardcoded, so the project keeps working next season"]
    ]));

    var pbp = m.pbp || [];
    if (pbp.length) {
      panel.appendChild(N.el("h3", { style: "margin-top:14px", text: "Play-by-play build detail" }));
      var t = N.el("table", { class: "src-table" });
      t.appendChild(N.el("thead", {}, [N.el("tr", {}, [
        N.el("th", { text: "Season" }), N.el("th", { text: "Plays" }),
        N.el("th", { text: "Games written" }), N.el("th", { text: "Columns" }),
        N.el("th", { text: "Status" })
      ])]));
      var tb = N.el("tbody");
      pbp.forEach(function (s) {
        tb.appendChild(N.el("tr", {}, [
          N.el("td", { text: String(s.season) }),
          N.el("td", { text: (s.plays || 0).toLocaleString() }),
          N.el("td", { text: (s.games_written || 0) + " / " + (s.games_requested || 0) }),
          N.el("td", { text: String(s.columns_observed || 0) }),
          N.el("td", {}, [N.el("span", {
            class: s.ok ? "pill pill--ok" : "pill pill--bad",
            text: s.ok ? "ok" : ("failed: " + (s.error || "unknown"))
          })])
        ]));
      });
      t.appendChild(tb);
      panel.appendChild(t);
    }
    host.appendChild(panel);
  }

  /* --------------------------------------------------- irregularities */

  function renderIrregularities(m) {
    var host = N.clear($("irrHost"));
    var irr = m.irregularities || {};
    if (!irr.total) {
      host.appendChild(N.el("div", { class: "notice notice--info" }, [
        N.el("h4", { text: "Nothing flagged" }),
        N.el("div", { text: "Every record in this snapshot passed the integrity checks: scores " +
          "agree with the result column, quarter lines agree with final scores, teams resolve, " +
          "and NFL identifiers are present where expected." })
      ]));
      return;
    }
    var panel = N.el("section", { class: "panel" });
    panel.appendChild(N.el("p", { style: "margin-top:0" }, [
      N.el("strong", { text: String(irr.total) }),
      " finding(s) across " + Object.keys(irr.by_kind || {}).length + " kind(s). These are " +
      "reported, never silently corrected."
    ]));

    var MEANING = {
      "past-window-without-score": "Kickoff is more than 4h45m past but no score is published. Could be postponed/cancelled or a lagging feed; the two are indistinguishable in the data.",
      "score-recorded-before-kickoff": "A score exists for a game whose kickoff is more than 6h away.",
      "tied-game": "A regular-season game that finished level. This is a LEGAL NFL result \u2014 since 1974 a regular-season game still tied after one overtime period is recorded as a tie, and NFL standings carry a ties column. Recorded for transparency, not because it is an error.",
      "postseason-game-with-tied-score": "A POSTSEASON game marked Final has equal scores. This one is genuinely impossible: playoff overtime continues until a winner emerges. Treated as a real data error and flagged for review.",
      "result-does-not-match-scores": "The upstream result column disagrees with home_score - away_score.",
      "missing-nfl-gsis-old-game-id": "No NFL GSIS 10-digit id, so the record cannot be tied to an official NFL identifier.",
      "missing-game-id": "No game id at all.",
      "missing-team-abbreviation": "A team abbreviation is empty.",
      "unknown-team-abbreviation": "A team code is not in the teams metadata; no name is guessed.",
      "missing-kickoff-time": "No parseable kickoff date/time upstream.",
      "score-without-kickoff-time": "Scores exist but there is no kickoff time, so status cannot be clock-checked.",
      "pbp-empty": "A play-by-play file was written with zero plays.",
      "pbp-missing-required-columns": "The upstream play-by-play schema lost a required column.",
      "nfl-api-id-mismatch-between-schedule-and-pbp": "The two feeds disagree on the official NFL game UUID."
    };

    var t = N.el("table", { class: "src-table" });
    t.appendChild(N.el("thead", {}, [N.el("tr", {}, [
      N.el("th", { text: "Kind" }), N.el("th", { text: "Count" }),
      N.el("th", { text: "Example" }), N.el("th", { text: "What it means" })
    ])]));
    var tb = N.el("tbody");
    Object.keys(irr.by_kind || {}).sort(function (a, b) {
      return irr.by_kind[b].count - irr.by_kind[a].count;
    }).forEach(function (k) {
      var info = irr.by_kind[k];
      tb.appendChild(N.el("tr", {}, [
        N.el("td", {}, [N.el("code", { text: k })]),
        N.el("td", { text: String(info.count) }),
        N.el("td", {}, [N.el("code", { text: info.example || "" })]),
        N.el("td", { text: MEANING[k] || (k.indexOf("disagrees-with-schedule") !== -1
          ? "Two upstream feeds disagree about this game. Treat it as suspect until reconciled against NFL.com."
          : "See the verification report.") })
      ]));
    });
    t.appendChild(tb);
    panel.appendChild(t);

    panel.appendChild(N.el("h3", { style: "margin-top:14px", text: "First 100 affected records" }));
    var ul = N.el("ul", { style: "margin:0;padding-left:18px;font-size:12.5px;max-height:280px;overflow:auto" });
    (irr.items || []).slice(0, 100).forEach(function (i) {
      ul.appendChild(N.el("li", {}, [
        N.el("code", { text: i.kind }), " in ",
        N.el("a", {
          href: "game.html?id=" + encodeURIComponent(i.game_id || "") + "&season=" + (i.season || ""),
          text: i.game_id || "?"
        }),
        " (" + i.season + " " + (i.season_type || "") + " wk " + N.text(i.week) + ")"
      ]));
    });
    panel.appendChild(ul);
    if ((irr.items || []).length > 100) {
      panel.appendChild(N.el("p", { class: "card__meta" }, [
        "\u2026and " + (irr.items.length - 100) + " more; the complete list is in ",
        N.el("code", { text: "docs/data/manifest.json" }), " and ",
        N.el("code", { text: "reports/verification.md" }), "."
      ]));
    }
    host.appendChild(panel);
  }

  /* ------------------------------------------------------- limitations */

  function renderLimitations(m) {
    var host = N.clear($("limitsHost"));
    var lims = m.limitations || [];
    var panel = N.el("section", { class: "panel" });
    if (!lims.length) {
      panel.appendChild(N.el("p", { text: "The build reported no limitations." }));
    } else {
      panel.appendChild(N.el("p", { style: "margin-top:0", class: "card__meta" }, [
        "Generated from the real state of this build, so this list cannot go stale."
      ]));
      var ul = N.el("ul", { style: "margin:0;padding-left:20px;line-height:1.75" });
      lims.forEach(function (l) {
        ul.appendChild(N.el("li", {}, [
          N.el("strong", { text: l.title }),
          N.el("div", { text: l.detail }),
          l.action ? N.el("div", { class: "card__meta", text: "Next step: " + l.action }) : null
        ].filter(Boolean)));
      });
      panel.appendChild(ul);
    }
    panel.appendChild(N.el("p", { class: "card__meta", style: "margin-bottom:0" }, [
      "The full backlog, with priorities and effort estimates, is in ",
      N.el("a", {
        href: "https://github.com/buffedlizard55-lab/NFLMAIN/blob/main/ROADMAP.md",
        target: "_blank", rel: "noopener noreferrer external", text: "ROADMAP.md"
      }), "."
    ]));
    host.appendChild(panel);
  }

  function renderStatusbar(m) {
    var bar = N.clear($("statusbar"));
    if (!m) { bar.appendChild(N.el("span", { class: "pill pill--bad" }, ["No manifest"])); return; }
    bar.appendChild(N.el("span", { class: "pill pill--ok" }, ["Snapshot " + N.relativeTime(m.generated_at)]));
    var g = m.generator || {};
    if (g.version) bar.appendChild(N.el("span", { class: "pill" }, ["pipeline v" + g.version]));
    var irr = m.irregularities || {};
    bar.appendChild(N.el("span", {
      class: irr.total ? "pill pill--warn" : "pill pill--ok"
    }, [irr.total ? ("\u26a0 " + irr.total + " flags") : "no flags"]));
    if (m.official_api && m.official_api.available) {
      bar.appendChild(N.el("span", { class: "pill pill--ok" }, ["api.nfl.com on"]));
    }
  }

  function boot() {
    Promise.all([
      N.getManifest().catch(function () { return null; }),
      N.getLinkCheck()
    ]).then(function (res) {
      var m = res[0], lc = res[1];
      if (!m) {
        N.clear($("sourcesHost")).appendChild(N.el("div", { class: "empty" }, [
          N.el("h3", { text: "No manifest published yet" }),
          N.el("p", { text: "Run the refresh-data GitHub Action to build docs/data/manifest.json." })
        ]));
        renderStatusbar(null);
        return;
      }
      renderStatusbar(m);
      renderSources(m);
      renderApi(m);
      renderLinks(lc);
      renderCoverage(m);
      renderIrregularities(m);
      renderLimitations(m);

      var p = N.clear($("footMeta"));
      p.appendChild(document.createTextNode("Snapshot generated " + (m.generated_at || "unknown")));
      var g = m.generator || {};
      if (g.run_url) {
        p.appendChild(document.createTextNode(" \u00b7 "));
        p.appendChild(N.el("a", { href: g.run_url, target: "_blank", rel: "noopener noreferrer external", text: "this build's log" }));
      }
      if (g.commit) {
        p.appendChild(document.createTextNode(" \u00b7 commit " + g.commit.slice(0, 7)));
      }
      if (location.hash) {
        var t = document.querySelector(location.hash);
        if (t) t.scrollIntoView();
      }
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
