/* Island Stay first-party analytics. Full tracking only after "Accept all" on the cookie banner;
   otherwise only an anonymous page count is sent. No third parties, no IP addresses stored. */
(function () {
  var ENDPOINT = '/t/', DAY = 864e5;
  function getCookie(n) { var m = document.cookie.match('(?:^|; )' + n + '=([^;]*)'); return m ? decodeURIComponent(m[1]) : ''; }
  function setCookie(n, v, days) { document.cookie = n + '=' + encodeURIComponent(v) + '; Max-Age=' + Math.round(days * 86400) + '; Path=/; SameSite=Lax' + (location.protocol === 'https:' ? '; Secure' : ''); }
  function uuid() { return (crypto.randomUUID && crypto.randomUUID()) || 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) { var r = Math.random() * 16 | 0; return (c === 'x' ? r : (r & 3 | 8)).toString(16); }); }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }

  /* ---------- cookie banner ---------- */
  var banner = document.getElementById('cookie-banner');
  function consent() { return getCookie('is_consent'); }
  function showBanner() { if (banner) { banner.hidden = false; } }
  function choose(level) {
    setCookie('is_consent', level, 180);
    if (level !== 'all') { setCookie('is_vid', '', -1); }
    if (banner) banner.hidden = true;
    try { document.dispatchEvent(new CustomEvent('is:consent', { detail: level })); } catch (e) {}
    start();
  }
  if (banner) {
    banner.querySelector('[data-consent=all]').addEventListener('click', function () { choose('all'); });
    banner.querySelector('[data-consent=necessary]').addEventListener('click', function () { choose('necessary'); });
  }
  document.querySelectorAll('[data-cookie-settings]').forEach(function (a) { a.addEventListener('click', function (e) { e.preventDefault(); showBanner(); }); });
  if (!consent()) showBanner();

  /* ---------- tracking ---------- */
  var path = location.pathname, queue = [], startedAt = Date.now(), maxScroll = 0, full = false, started = false;
  if (/^\/(dashboard|accounts|admin)\//.test(path)) return;

  function session() {
    var now = Date.now(), sid = store('is_sid'), last = +(store('is_sid_t') || 0);
    if (!sid || now - last > 30 * 60 * 1000) { sid = uuid(); store('is_sid', sid); }
    store('is_sid_t', String(now));
    return sid;
  }
  function track(type, label, value, extra) {
    if (!started || (!full && type !== 'pageview')) return;
    var e = { type: type, path: path, label: (label || '').toString().trim().replace(/\s+/g, ' ').slice(0, 200), value: (value || '').toString().slice(0, 300), at: Date.now() };
    if (extra) for (var k in extra) e[k] = extra[k];
    queue.push(e);
    if (type !== 'scroll') flush();  // send right away: a click or search usually leaves the page
  }
  function flush() {
    if (!queue.length) return;
    var now = Date.now();
    var batch = queue.splice(0, 60).map(function (e) { e.t = now - e.at; delete e.at; return e; });
    var body = JSON.stringify({ vid: full ? getCookie('is_vid') : '', sid: full ? session() : '', lang: navigator.language, screen: screen.width + 'x' + screen.height, events: batch });
    if (!(navigator.sendBeacon && navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'text/plain' })))) {
      fetch(ENDPOINT, { method: 'POST', body: body, keepalive: true, credentials: 'same-origin' }).catch(function () {});
    }
  }
  window.isTrack = track;

  function start() {
    if (started) return;
    var c = consent(); if (!c) return;
    started = true; full = c === 'all';
    if (full && !getCookie('is_vid')) setCookie('is_vid', uuid(), 395);
    if (full) setCookie('is_vid', getCookie('is_vid'), 395);  // keep it alive
    if (full) {
      try {
        var pending = JSON.parse(sessionStorage.getItem('is_leave') || 'null'); sessionStorage.removeItem('is_leave');
        if (pending) queue.push({ type: 'leave', path: pending.path, label: pending.label, value: pending.value, at: Date.now() - 1 });
      } catch (e) {}
    }
    var q = new URLSearchParams(location.search);
    track('pageview', document.title, location.search.slice(0, 300), {
      referrer: document.referrer, utm_source: q.get('utm_source') || '', utm_medium: q.get('utm_medium') || '', utm_campaign: q.get('utm_campaign') || ''
    });
    if (!full) return;
    if (document.querySelector('.rq-error-summary')) track('request_error', document.querySelector('.rq-error-summary').innerText.slice(0, 200));
    setInterval(flush, 5000);
  }

  /* clicks on links and buttons */
  document.addEventListener('click', function (ev) {
    var el = ev.target.closest('a, button, summary, [data-track]'); if (!el) return;
    var label = el.getAttribute('data-track') || el.getAttribute('aria-label') || el.innerText || el.title || '';
    var href = el.getAttribute('href') || '';
    if (el.matches('.send-btn')) return;  // recorded separately
    if (href && /^https?:/.test(href) && el.host !== location.host) track('outbound', label, href);
    else track('click', label, href);
  }, true);

  /* searches and filters */
  document.addEventListener('submit', function (ev) {
    var f = ev.target;
    if (f.id === 'rq-form') { track('request_submit', 'Send request'); return; }
    var data = new FormData(f), q = data.get('q');
    if (f.getAttribute('role') === 'search' || (q && f.method.toLowerCase() === 'get' && data.getAll('q').length && !f.querySelector('select'))) { track('search', 'Search', q); return; }
    if (f.method.toLowerCase() === 'get') {
      var parts = []; data.forEach(function (v, k) { if (v) parts.push(k + '=' + v); });
      track('filter', 'Filters', parts.join('&'));
    }
  }, true);

  /* request form: first interaction */
  var rq = document.getElementById('rq-form');
  if (rq) rq.addEventListener('focusin', function once() { track('request_start', 'Started request form'); rq.removeEventListener('focusin', once); });

  /* send-to-host buttons on the confirmation page */
  document.querySelectorAll('[data-send]').forEach(function (b) {
    b.addEventListener('click', function () {
      var ch = b.getAttribute('data-send'), ref = b.getAttribute('data-ref');
      track('send_to_host', ch, ref);
      var fd = new FormData(); fd.append('channel', ch); fd.append('csrfmiddlewaretoken', getCookie('csrftoken'));
      navigator.sendBeacon ? navigator.sendBeacon(b.getAttribute('data-via-url'), fd) : fetch(b.getAttribute('data-via-url'), { method: 'POST', body: fd, keepalive: true });
    });
  });

  /* scroll depth */
  var marks = [25, 50, 75, 100];
  addEventListener('scroll', function () {
    var h = document.documentElement, pct = Math.round((h.scrollTop + innerHeight) / h.scrollHeight * 100);
    if (pct > maxScroll) { maxScroll = pct; while (marks.length && pct >= marks[0]) track('scroll', marks.shift() + '%'); }
  }, { passive: true });

  /* time on page */
  var visibleMs = 0, visibleSince = document.hidden ? 0 : Date.now(), leaveSent = false;
  function leave() {
    if (visibleSince) visibleMs += Date.now() - visibleSince;
    visibleSince = 0;
    if (!leaveSent) { leaveSent = true; track('leave', Math.round(visibleMs / 1000) + 's', String(Math.min(maxScroll, 100))); }
    flush();
  }
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) leave();
    else { visibleSince = Date.now(); leaveSent = false; }
  });
  // Navigating to another page: hand the time and scroll to the next page to send, in case this beacon is dropped.
  addEventListener('pagehide', function () {
    if (!full || leaveSent) return flush();
    if (visibleSince) visibleMs += Date.now() - visibleSince;
    visibleSince = 0; leaveSent = true;
    try { sessionStorage.setItem('is_leave', JSON.stringify({ path: path, label: Math.round(visibleMs / 1000) + 's', value: String(Math.min(maxScroll, 100)) })); } catch (e) {}
    flush();
  });

  start();
})();
