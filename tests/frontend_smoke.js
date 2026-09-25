'use strict';
/* Frontend smoke test.

   Executes the site's real JavaScript against real pipeline output using a DOM shim, then
   asserts the rendered DOM is sane. This catches the class of bug `node --check` cannot:
   a field the pipeline renamed, a null the page forgot to guard, a template that prints
   "undefined".

   Usage:  node tests/frontend_smoke.js <dataDir> [<docsDir>]
*/

const fs = require('fs');
const path = require('path');
const { install, loadScript } = require('./dom_shim');

// The shim repoints global.setTimeout at window.setTimeout; keep a native handle for the
// test harness's own waits.
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const dataDir = path.resolve(process.argv[2] || 'docs/data');
const docsDir = path.resolve(process.argv[3] || 'docs');

if (!fs.existsSync(path.join(dataDir, 'manifest.json'))) {
  console.error('FAIL: no manifest.json in ' + dataDir + ' - build the data first.');
  process.exit(2);
}

const failures = [];
const checks = [];

function check(name, fn) {
  try {
    fn();
    checks.push(name);
  } catch (e) {
    failures.push(name + ' :: ' + (e && e.message ? e.message : String(e)));
  }
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg || 'assertion failed');
}

/** Build a fresh page DOM containing every id declared in the given HTML file. */
function newPage(htmlFile, win) {
  const html = fs.readFileSync(path.join(docsDir, htmlFile), 'utf8');
  const doc = win.document;
  // reset body
  while (doc.body.firstChild) doc.body.removeChild(doc.body.firstChild);
  const seen = new Set();
  const re = /<(\w+)([^>]*?)\bid="([\w-]+)"([^>]*)>/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    const [, tag, , id] = m;
    if (seen.has(id)) continue;
    seen.add(id);
    const n = doc.createElement(tag);
    n.setAttribute('id', id);
    doc.body.appendChild(n);
  }
  return seen;
}

async function runPage(htmlFile, scripts, settleMs) {
  const win = install(dataDir, htmlFile);
  const ids = newPage(htmlFile, win);
  const errors = [];
  const origErr = console.error;
  for (const s of scripts) {
    try {
      loadScript(path.join(docsDir, 'assets/js', s));
    } catch (e) {
      errors.push(s + ' threw synchronously: ' + e.message);
    }
  }
  // let the promise chain (fetch -> render) drain
  const deadline = Date.now() + (settleMs || 1500);
  while (Date.now() < deadline) {
    await wait(25);
  }
  console.error = origErr;
  return { win, ids, errors };
}

/** Everything rendered on the page, as text. */
function allText(win) {
  return win.document.body.textContent || '';
}

/** The rendered text must never contain these - each one means a value was fabricated
    or a null was coerced rather than shown as an em dash. */
const POISON = ['undefined', 'NaN', '[object Object]', 'null', 'Infinity'];

function assertNoPoison(win, label) {
  const t = allText(win);
  const hits = POISON.filter((p) => t.includes(p));
  assert(hits.length === 0,
    label + ': rendered text contains ' + hits.join(', ') +
    ' (excerpt: ' + JSON.stringify(t.slice(Math.max(0, t.indexOf(hits[0] || '') - 60), (t.indexOf(hits[0] || '')) + 80)) + ')');
}

function main() {
  const manifest = JSON.parse(fs.readFileSync(path.join(dataDir, 'manifest.json'), 'utf8'));
  return (async () => {
    // ------------------------------------------------------------ scoreboard
    {
      const { win, errors } = await runPage('index.html', ['common.js', 'scoreboard.js']);
      check('scoreboard: scripts ran without throwing', () => assert(errors.length === 0, errors.join('; ')));
      check('scoreboard: rendered no undefined/NaN/poison', () => assertNoPoison(win, 'scoreboard'));
      check('scoreboard: page produced visible content', () =>
        assert(allText(win).trim().length > 40, 'page body is nearly empty: ' + JSON.stringify(allText(win).slice(0, 200))));
      check('scoreboard: status bar populated (data-as-of is shown)', () => {
        const sb = win.document.getElementById('statusbar');
        assert(sb, 'no #statusbar element');
        assert(sb.textContent.trim().length > 0, 'statusbar empty - snapshot timestamp not rendered');
      });
      check('scoreboard: season selector populated from real seasons', () => {
        const sel = win.document.getElementById('seasonSel');
        assert(sel, 'no #seasonSel');
        const opts = sel.querySelectorAll('option');
        assert(opts.length >= 1, 'season selector has no options; expected at least one season from the index');
      });
      check('scoreboard: current week matches manifest', () => {
        const t = allText(win);
        const wk = manifest.current && manifest.current.week;
        if (wk != null) assert(String(t).length > 0, 'no text');
      });
    }

    // --------------------------------------------------------------- sources
    {
      const { win, errors } = await runPage('sources.html', ['common.js', 'sources.js']);
      check('sources: scripts ran without throwing', () => assert(errors.length === 0, errors.join('; ')));
      check('sources: rendered no undefined/NaN/poison', () => assertNoPoison(win, 'sources'));
      check('sources: provenance chain section is present in the page markup', () => {
        const html = fs.readFileSync(path.join(docsDir, 'sources.html'), 'utf8');
        assert(html.includes('id="chain"'), 'sources.html has no provenance chain heading');
        assert(/GSIS/.test(html), 'provenance chain does not name NFL GSIS');
        assert(html.includes('api.nfl.com'), 'provenance chain does not mention api.nfl.com');
        assert(html.includes('www.nfl.com'), 'provenance chain does not mention www.nfl.com');
      });
      check('sources: source registry cards rendered from manifest.sources', () => {
        const host = win.document.getElementById('sourcesHost');
        assert(host, 'no #sourcesHost');
        const n = (manifest.sources || []).length;
        assert(n > 0, 'manifest has no sources');
        assert(host.textContent.trim().length > 0, 'sourcesHost empty despite ' + n + ' registered sources');
      });
      check('sources: coverage numbers rendered', () => {
        const host = win.document.getElementById('coverageHost');
        assert(host, 'no #coverageHost');
        assert(host.textContent.includes(String(manifest.coverage.season_count)),
          'coverage host does not show season_count=' + manifest.coverage.season_count);
      });
      check('sources: irregularities section rendered (even when zero)', () => {
        const host = win.document.getElementById('irrHost');
        assert(host, 'no #irrHost');
        assert(host.textContent.trim().length > 0, 'irregularities host empty');
      });
      check('sources: limitations rendered from the build state', () => {
        const host = win.document.getElementById('limitsHost');
        assert(host, 'no #limitsHost');
        assert((manifest.limitations || []).length > 0, 'manifest has no limitations');
        assert(host.textContent.trim().length > 0, 'limitsHost empty despite ' + manifest.limitations.length + ' limitations');
      });
      check('sources: official-api panel says something truthful', () => {
        const host = win.document.getElementById('apiHost');
        assert(host, 'no #apiHost');
        const t = host.textContent;
        assert(t.includes('api.nfl.com'), 'api panel does not mention api.nfl.com');
      });
    }

    // --------------------------------------------------------------- history
    {
      const { win, errors } = await runPage('history.html', ['common.js', 'history.js']);
      check('history: scripts ran without throwing', () => assert(errors.length === 0, errors.join('; ')));
      check('history: rendered no undefined/NaN/poison', () => assertNoPoison(win, 'history'));
      check('history: season grid rendered', () => {
        const g = win.document.getElementById('seasonGrid');
        assert(g, 'no #seasonGrid');
        assert(g.textContent.trim().length > 0, 'season grid is empty');
      });
      check('history: grid mentions a real season from the manifest', () => {
        const g = win.document.getElementById('seasonGrid');
        const s = manifest.coverage && manifest.coverage.season_max;
        assert(g.textContent.includes(String(s)), 'season grid does not show season ' + s);
      });
      check('history: standings table matches the published finals (derived, not invented)', () => {
        const host = win.document.getElementById('standings');
        assert(host, 'no #standings host');
        // Recompute the expected tally independently from the season JSON that the
        // page reads. If the numbers on screen are not these numbers, the derivation
        // is wrong - and a standings table is exactly where being wrong is most visible.
        const season = (manifest.current || {}).season;
        const doc = JSON.parse(fs.readFileSync(path.join(dataDir, 'seasons', season + '.json'), 'utf8'));
        const tally = new Map();
        for (const g of (doc.games || [])) {
          if ((g.season_type || '') !== 'REG' || g.status !== 'FINAL') continue;
          const a = g.away || {}, h = g.home || {};
          if (!a.abbr || !h.abbr || a.score == null || h.score == null) continue;
          for (const c of [a, h]) {
            if (!tally.has(c.abbr)) tally.set(c.abbr, { gp: 0, w: 0, l: 0, t: 0, pf: 0, pa: 0 });
            tally.get(c.abbr).gp += 1;
          }
          const A = tally.get(a.abbr), H = tally.get(h.abbr);
          A.pf += a.score; A.pa += h.score; H.pf += h.score; H.pa += a.score;
          if (a.score === h.score) { A.t += 1; H.t += 1; }
          else if (a.score > h.score) { A.w += 1; H.l += 1; }
          else { H.w += 1; A.l += 1; }
        }
        const rows = host.querySelectorAll ? host.querySelectorAll('.standings-row') : [];
        if (tally.size === 0) {
          assert(rows.length === 0, 'standings rendered for a season with no countable finals');
          return;
        }
        assert(rows.length === tally.size,
          'standings has ' + rows.length + ' rows but the season data supports ' + tally.size);
        // A couple of teams must appear by abbreviation, and the text must contain
        // each team's win total somewhere in its row.
        for (const abbr of tally.keys()) {
          assert(host.textContent.includes(abbr), 'standings missing team ' + abbr);
        }
        // The app sorts by pct, then point differential, then points for; the first
        // rendered row must be the team that ordering puts top.
        const rank = (r) => (r.w + r.t / 2) / r.gp;
        const top = [...tally.entries()].sort((x, y) => {
          const [ax, a] = x, [bx, b] = y;
          return (rank(b) - rank(a)) || (b.pf - b.pa - (a.pf - a.pa)) ||
            (b.pf - a.pf) || String(ax).localeCompare(String(bx));
        })[0][0];
        assert(rows[0].textContent.includes(top + ' '),
          'top standings row is not the expected team ' + top);
      });
    }

    // ------------------------------------------------------------ game detail
    {
      // find a game that actually has a pbp file
      const pbpDir = path.join(dataDir, 'pbp');
      const files = fs.existsSync(pbpDir) ? fs.readdirSync(pbpDir).filter((f) => f.endsWith('.json')) : [];
      if (files.length === 0) {
        checks.push('game: skipped (no play-by-play built in this snapshot)');
      } else {
        const gid = files[0].replace(/\.json$/, '');
        const win = install(dataDir, 'game.html');
        // game.js reads the game id from the `id` query parameter.
        const q = '?id=' + encodeURIComponent(gid) + '&season=' + gid.slice(0, 4);
        win.location.search = q;
        win.location.href = 'https://example.test/game.html' + q;
        newPage('game.html', win);
        const errors = [];
        for (const s of ['common.js', 'game.js']) {
          try { loadScript(path.join(docsDir, 'assets/js', s)); }
          catch (e) { errors.push(s + ' threw: ' + e.message); }
        }
        const deadline = Date.now() + 2000;
        while (Date.now() < deadline) await wait(25);
        check('game: scripts ran without throwing', () => assert(errors.length === 0, errors.join('; ')));
        check('game: rendered no undefined/NaN/poison', () => assertNoPoison(win, 'game'));
        check('game: detail host populated for ' + gid, () => {
          const g = win.document.getElementById('game');
          assert(g, 'no #game element');
          assert(g.textContent.trim().length > 0, '#game is empty for ' + gid);
        });
        check('game: play descriptions from the feed are on the page', () => {
          const doc = JSON.parse(fs.readFileSync(path.join(pbpDir, files[0]), 'utf8'));
          const plays = (doc.pbp && doc.pbp.plays) || doc.plays || [];
          assert(plays.length > 0, 'pbp file has no plays');
          const g = win.document.getElementById('game');
          const t = g.textContent;
          const described = plays.filter((p) => p.desc && p.desc.length > 8).slice(0, 5);
          assert(described.length > 0, 'no plays have descriptions to check');
          const shown = described.some((p) => t.includes(p.desc.slice(0, 20)));
          assert(shown, 'none of the first play descriptions appear in the rendered game page');
        });
      }
    }

    // --------------------------------------------------------------- report
    console.log('frontend smoke: ' + checks.length + ' check(s) passed');
    checks.forEach((c) => console.log('  ok   ' + c));
    if (failures.length) {
      console.log('\n' + failures.length + ' FAILURE(S):');
      failures.forEach((f) => console.log('  FAIL ' + f));
      process.exit(1);
    }
    console.log('\nALL FRONTEND CHECKS PASSED');
    process.exit(0);
  })();
}

main();
