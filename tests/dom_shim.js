// Minimal DOM + fetch shim so the site's vanilla JS can be executed and asserted on in
// CI, where there is no browser. This exists because "the JS parses" (node --check) is a
// much weaker claim than "the JS renders the real data shape without throwing".
//
// It implements only what docs/assets/js/* uses: createElement, appendChild, textContent,
// className, setAttribute, addEventListener, querySelector(All) by #id and .class,
// getElementById, and fetch() backed by files on disk.

'use strict';

const fs = require('fs');
const path = require('path');

class ClassList {
  constructor(node) { this.node = node; }
  get _set() {
    return new Set((this.node.className || '').split(/\s+/).filter(Boolean));
  }
  add(...c) { const s = this._set; c.forEach((x) => x && s.add(x)); this.node.className = [...s].join(' '); }
  remove(...c) { const s = this._set; c.forEach((x) => s.delete(x)); this.node.className = [...s].join(' '); }
  contains(c) { return this._set.has(c); }
  toggle(c, on) { if (on === undefined) on = !this.contains(c); on ? this.add(c) : this.remove(c); return on; }
}

let _idCounter = 0;

class Node {
  constructor(tag) {
    this.tagName = String(tag || 'div').toUpperCase();
    this.childNodes = [];
    this.parentNode = null;
    this.attributes = {};
    this.className = '';
    this._text = null;
    this.style = {};
    this.classList = new ClassList(this);
    this.listeners = {};
    this.value = '';
    this.checked = false;
    this.disabled = false;
    this.href = '';
    this.scrollTop = 0;
    this.scrollHeight = 1000;
    this.clientHeight = 500;
    this.dataset = {};
    this._uid = ++_idCounter;
  }

  get firstChild() { return this.childNodes[0] || null; }
  get lastChild() { return this.childNodes[this.childNodes.length - 1] || null; }
  get children() { return this.childNodes.filter((n) => n instanceof Node); }

  appendChild(c) {
    if (!c) throw new Error('appendChild(null)');
    if (c.parentNode) c.parentNode.removeChild(c);
    c.parentNode = this;
    this.childNodes.push(c);
    this._text = null; // explicit children win over textContent
    return c;
  }

  removeChild(c) {
    const i = this.childNodes.indexOf(c);
    if (i >= 0) { this.childNodes.splice(i, 1); c.parentNode = null; }
    return c;
  }

  insertBefore(c, ref) {
    const i = this.childNodes.indexOf(ref);
    if (i < 0) return this.appendChild(c);
    if (c.parentNode) c.parentNode.removeChild(c);
    c.parentNode = this;
    this.childNodes.splice(i, 0, c);
    return c;
  }

  set textContent(v) {
    this._text = v === null || v === undefined ? '' : String(v);
    this.childNodes.forEach((c) => { c.parentNode = null; });
    this.childNodes = [];
  }
  get textContent() {
    if (this.childNodes.length === 0) return this._text === null ? '' : this._text;
    return this.childNodes.map((c) => (c instanceof Node ? c.textContent : String(c))).join('');
  }

  set innerHTML(v) { this.textContent = v; } // good enough; the site never injects untrusted HTML
  get innerHTML() { return this.textContent; }

  setAttribute(k, v) {
    this.attributes[k] = String(v);
    if (k === 'class') this.className = String(v);
    if (k === 'id') this.id = String(v);
    if (k === 'href') this.href = String(v);
    if (k === 'value') this.value = String(v);
    if (k === 'disabled') this.disabled = true;
    if (k.startsWith('data-')) this.dataset[k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = String(v);
  }
  getAttribute(k) { return k in this.attributes ? this.attributes[k] : null; }
  hasAttribute(k) { return k in this.attributes; }
  removeAttribute(k) { delete this.attributes[k]; }

  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  removeEventListener(type, fn) {
    const a = this.listeners[type] || [];
    const i = a.indexOf(fn);
    if (i >= 0) a.splice(i, 1);
  }
  dispatchEvent(type, ev) {
    (this.listeners[type] || []).forEach((fn) => fn.call(this, ev || { target: this, preventDefault() {}, stopPropagation() {} }));
    if (this.parentNode) this.parentNode.dispatchEvent(type, ev); // crude bubbling
  }
  click() { this.dispatchEvent('click', { target: this, preventDefault() {}, stopPropagation() {} }); }
  focus() {}
  blur() {}
  scrollIntoView() {}
  contains(n) {
    if (n === this) return true;
    return this.childNodes.some((c) => c instanceof Node && c.contains(n));
  }
  closest() { return null; }

  // --- traversal -------------------------------------------------------- //
  _walk() {
    const out = [];
    for (const c of this.childNodes) {
      if (c instanceof Node) { out.push(c); out.push(...c._walk()); }
    }
    return out;
  }
  querySelectorAll(sel) {
    return this._walk().filter((n) => n._matches(sel.trim()));
  }
  querySelector(sel) {
    const s = String(sel).trim();
    if (s.includes(',')) {
      for (const part of s.split(',')) { const m = this.querySelector(part); if (m) return m; }
      return null;
    }
    return this._walk().find((n) => n._matches(s)) || null;
  }
  getElementById(id) {
    if (this.id === id) return this;
    return this._walk().find((n) => n.id === id) || null;
  }
  getElementsByTagName(t) {
    const up = String(t).toUpperCase();
    return this._walk().filter((n) => n.tagName === up);
  }
  _matches(sel) {
    // supports "#id", ".class", "tag", ".a.b", "tag.class", "[attr]", and simple
    // descendant chains by matching the LAST compound only (adequate for this site).
    const parts = sel.split(/\s+/);
    const last = parts[parts.length - 1];
    if (parts.length > 1 && !this._matchSimple(last)) return false;
    if (parts.length > 1 && !this._hasAncestorMatching(parts.slice(0, -1).join(' '))) return false;
    return this._matchSimple(last);
  }
  _hasAncestorMatching(sel) {
    let p = this.parentNode;
    while (p) { if (p._matches(sel)) return true; p = p.parentNode; }
    return false;
  }
  _matchSimple(sel) {
    if (!sel) return false;
    if (sel.startsWith('#')) return this.id === sel.slice(1);
    const m = sel.match(/^([a-zA-Z]*)((?:\.[\w-]+)*)((?:\[[^\]]+\])*)$/);
    if (!m) return false;
    const [, tag, classes, attrs] = m;
    if (tag && this.tagName !== tag.toUpperCase()) return false;
    if (classes) {
      for (const c of classes.split('.').filter(Boolean)) if (!this.classList.contains(c)) return false;
    }
    if (attrs) {
      for (const a of attrs.match(/\[[^\]]+\]/g) || []) {
        const name = a.slice(1, -1).split('=')[0];
        if (!this.hasAttribute(name)) return false;
      }
    }
    return true;
  }
}

class TextNode extends Node {
  constructor(text) { super('#text'); this._text = String(text); }
  get textContent() { return this._text; }
  set textContent(v) { this._text = String(v); }
}

// Captured BEFORE install() overwrites the globals, otherwise win.setTimeout recurses
// into itself once global.setTimeout points back at it.
const nativeSetTimeout = setTimeout;
const nativeClearTimeout = clearTimeout;
const nativeSetInterval = setInterval;
const nativeClearInterval = clearInterval;

install.pageName = 'index.html';

function install(dataDir, pageName) {
  if (pageName) install.pageName = pageName;
  const document = new Node('#document');
  document.documentElement = document.appendChild(new Node('html'));
  document.body = document.appendChild(new Node('body'));
  document.head = document.appendChild(new Node('head'));
  document.title = '';
  document.readyState = 'complete';
  document.location = {
    href: 'https://example.test/',
    search: '',
    hash: '',
    pathname: '/' + (install.pageName || 'index.html'),
  };
  document.createElement = (t) => new Node(t);
  document.createTextNode = (t) => new TextNode(t);
  document.createDocumentFragment = () => new Node('#fragment');
  document.addEventListener = () => {};
  document.removeEventListener = () => {};

  const win = {
    document,
    location: document.location,
    navigator: { userAgent: 'node-dom-shim' },
    addEventListener(type, fn) { (this._l = this._l || {})[type] = (this._l[type] || []).concat([fn]); },
    removeEventListener() {},
    dispatch(type, ev) { ((this._l || {})[type] || []).forEach((f) => f(ev || {})); },
    setTimeout: (fn, ms) => nativeSetTimeout(fn, ms || 0),
    clearTimeout: (h) => nativeClearTimeout(h),
    setInterval: () => 0,
    clearInterval: () => {},
    requestAnimationFrame: (fn) => nativeSetTimeout(() => fn(Date.now()), 0),
    matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
    localStorage: (() => {
      const m = new Map();
      return {
        getItem: (k) => (m.has(k) ? m.get(k) : null),
        setItem: (k, v) => m.set(k, String(v)),
        removeItem: (k) => m.delete(k),
        clear: () => m.clear(),
      };
    })(),
    history: { pushState() {}, replaceState() {} },
    scrollTo() {},
    fetch(url, opts) {
      // Resolve site-relative data URLs against the fixture-built data directory.
      // The page computes BASE from location.pathname, so URLs arrive as
      // "/data/manifest.json" when served at a site root, or "data/x.json" locally.
      let rel = String(url).split('?')[0].split('#')[0];
      const marker = '/data/';
      const at = rel.indexOf(marker);
      if (at >= 0) rel = rel.slice(at + marker.length);
      else if (rel.startsWith('data/')) rel = rel.slice('data/'.length);
      else rel = rel.replace(/^\/+/, '');
      const full = path.join(dataDir, rel);
      return Promise.resolve().then(() => {
        if (!fs.existsSync(full)) {
          const err = new Error('HTTP 404 (shim): ' + full);
          return { ok: false, status: 404, json: () => Promise.reject(err), text: () => Promise.reject(err) };
        }
        const body = fs.readFileSync(full, 'utf8');
        return {
          ok: true, status: 200,
          json: () => Promise.resolve(JSON.parse(body)),
          text: () => Promise.resolve(body),
        };
      });
    },
  };

  // Node >=21 defines some of these as getter-only globals, so assignment throws.
  // Use defineProperty and ignore failures - the scripts read them off `window` anyway.
  const defineGlobal = (name, value) => {
    try {
      Object.defineProperty(global, name, {
        value, writable: true, configurable: true, enumerable: true,
      });
    } catch (_) { /* already defined and non-configurable; window.<name> still works */ }
  };
  defineGlobal('window', win);
  defineGlobal('document', document);
  defineGlobal('location', win.location);
  defineGlobal('navigator', win.navigator);
  defineGlobal('localStorage', win.localStorage);
  global.fetch = win.fetch;
  defineGlobal('setTimeout', win.setTimeout);
  defineGlobal('clearTimeout', win.clearTimeout);
  defineGlobal('setInterval', win.setInterval);
  defineGlobal('clearInterval', win.clearInterval);
  defineGlobal('requestAnimationFrame', win.requestAnimationFrame);
  defineGlobal('matchMedia', win.matchMedia);
  defineGlobal('history', win.history);
  defineGlobal('screen', { width: 1280, height: 800 });
  defineGlobal('getComputedStyle', () => ({ getPropertyValue: () => '' }));
  defineGlobal('Image', function () { return new Node('img'); });
  defineGlobal('Event', function (t) { this.type = t; });
  defineGlobal('URL', URL);
  global.Node = Node;
  return win;
}

function loadScript(file) {
  const src = fs.readFileSync(file, 'utf8');
  // Scripts run in the shared global scope, exactly as they do in a browser.
  // eslint-disable-next-line no-new-func
  new Function(src).call(global);
}

module.exports = { install, loadScript, Node, TextNode };
