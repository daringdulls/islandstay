/* Page motion: reveal sections as they scroll into view and count numbers up. Everything is visible
   without JavaScript and for visitors who prefer reduced motion. */
(function () {
  "use strict";
  var root = document.documentElement;
  if (!root.classList.contains("motion")) return;

  var reveal = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window)) {
    reveal.forEach(function (el) { el.classList.add("in"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    reveal.forEach(function (el, i) {
      el.style.setProperty("--d", (el.dataset.delay || 0) + "ms");
      io.observe(el);
    });
  }

  document.querySelectorAll("[data-count]").forEach(function (el) {
    var target = parseInt(el.getAttribute("data-count"), 10) || 0, start = null, dur = 1400;
    el.textContent = "0";
    function step(t) {
      if (!start) start = t;
      var p = Math.min((t - start) / dur, 1);
      el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))).toLocaleString();
      if (p < 1) requestAnimationFrame(step);
    }
    setTimeout(function () { requestAnimationFrame(step); }, 500);
  });
})();

/* Saved islands and listings. Kept in this browser only (no account needed); the Saved page receives the
   list in its URL, so it can also be shared on WhatsApp or by link. */
(function () {
  "use strict";
  var KEY = "is_saved";
  function read() { try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; } }
  function write(list) { try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) {} }
  function url(list) {
    var i = [], l = [];
    list.forEach(function (k) { (k.slice(0, 2) === "i:" ? i : l).push(k.slice(2)); });
    var q = [];
    if (i.length) q.push("i=" + i.join(","));
    if (l.length) q.push("l=" + l.join(","));
    return "/saved/" + (q.length ? "?" + q.join("&") : "?i=");
  }
  function paint() {
    var list = read();
    document.querySelectorAll("[data-save]").forEach(function (b) {
      var on = list.indexOf(b.getAttribute("data-save")) > -1;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
      var lbl = b.querySelector("[data-save-label]");
      if (lbl) lbl.textContent = on ? "Saved" : "Save";
    });
    document.querySelectorAll("[data-saved-count]").forEach(function (n) {
      n.textContent = list.length; n.hidden = !list.length;
    });
    document.querySelectorAll("[data-saved-link]").forEach(function (a) { a.href = url(list); });
  }
  window.isSaved = { read: read, url: url };
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-save]");
    if (!b) return;
    e.preventDefault();
    var key = b.getAttribute("data-save"), list = read(), at = list.indexOf(key);
    if (at > -1) list.splice(at, 1); else list.unshift(key);
    write(list.slice(0, 40));
    paint();
    if (window.isTrack) window.isTrack(at > -1 ? "unsave" : "save", key);
    var remove = b.closest("[data-saved-item]");
    if (remove && at > -1) remove.remove();
  });
  // Opening /saved/ without a list: load the one kept in this browser.
  if (location.pathname === "/saved/" && !location.search) {
    var list = read();
    if (list.length) location.replace(url(list));
  }
  paint();
  // Copy-link buttons
  document.querySelectorAll("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var text = b.getAttribute("data-copy");
      (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function () {
        var old = b.innerHTML; b.textContent = "Link copied"; setTimeout(function () { b.innerHTML = old; }, 1800);
      }).catch(function () { window.prompt("Copy this link", text); });
    });
  });
})();

/* Type-ahead suggestions for any search box marked data-suggest. */
(function () {
  "use strict";
  var iconUrl = (function () { var u = document.querySelector("svg.i use"); return u ? u.getAttribute("href").split("#")[0] : "/static/img/icons.svg"; })();
  function esc(s) { return String(s || "").replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  document.querySelectorAll("input[data-suggest]").forEach(function (input) {
    var host = input.closest("form") || input.parentNode, box = document.createElement("div"), timer, items = [], active = -1, last = "";
    box.className = "suggest"; box.setAttribute("role", "listbox"); box.hidden = true;
    host.classList.add("has-suggest"); host.appendChild(box);
    input.setAttribute("aria-autocomplete", "list");
    function close() { box.hidden = true; active = -1; }
    function render(data) {
      items = data.items || [];
      if (!items.length) { box.innerHTML = '<div class="suggest-none">No matches yet. Press Enter to search everything.</div>'; box.hidden = false; return; }
      box.innerHTML = items.map(function (it, n) {
        return '<a role="option" class="suggest-item" data-n="' + n + '" href="' + esc(it.url) + '"><svg class="i" aria-hidden="true"><use href="' + iconUrl + '#' + esc(it.icon) + '"></use></svg>' +
          '<span><b>' + esc(it.label) + '</b><small>' + esc(it.sub) + '</small></span><em>' + esc(it.t) + '</em></a>';
      }).join("") + '<a class="suggest-all" href="' + esc(data.all) + '">See all results for “' + esc(input.value) + '”</a>';
      box.hidden = false;
    }
    input.addEventListener("input", function () {
      var q = input.value.trim();
      clearTimeout(timer);
      if (q.length < 2) { close(); return; }
      timer = setTimeout(function () {
        if (q === last) { box.hidden = false; return; }
        last = q;
        fetch("/search/suggest/?q=" + encodeURIComponent(q)).then(function (r) { return r.json(); }).then(function (d) { if (input.value.trim() === q) render(d); }).catch(close);
      }, 160);
    });
    input.addEventListener("keydown", function (e) {
      var links = box.querySelectorAll(".suggest-item");
      if (box.hidden || !links.length) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        active = (active + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
        links.forEach(function (l, n) { l.classList.toggle("on", n === active); });
      } else if (e.key === "Enter" && active > -1) {
        e.preventDefault(); location.href = links[active].href;
      } else if (e.key === "Escape") { close(); }
    });
    input.addEventListener("focus", function () { if (box.innerHTML && input.value.trim().length > 1) box.hidden = false; });
    document.addEventListener("click", function (e) { if (!host.contains(e.target)) close(); });
  });
})();

/* Close the header "More" menu when clicking elsewhere or pressing Escape. */
(function () {
  var more = document.querySelector(".nav-more");
  if (!more) return;
  document.addEventListener("click", function (e) { if (more.open && !more.contains(e.target)) more.open = false; });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && more.open) { more.open = false; more.querySelector("summary").focus(); } });
})();

/* Arrival planner on island pages: which routes still work for a given landing time and day. */
(function () {
  document.querySelectorAll('.ap').forEach(function (ap) {
    var scope = ap.parentNode;
    var routes = scope.querySelectorAll('.route');
    var time = ap.querySelector('[data-ap=time]'), day = ap.querySelector('[data-ap=day]'), out = ap.querySelector('.ap-out');
    var names = { mon: 'Monday', tue: 'Tuesday', wed: 'Wednesday', thu: 'Thursday', fri: 'Friday', sat: 'Saturday', sun: 'Sunday' };
    day.value = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'][new Date().getDay()];
    function mins(t) { var p = (t || '').split(':'); return p.length === 2 ? (+p[0]) * 60 + (+p[1]) : null; }
    function update() {
      var ready = mins(time.value) + 60, d = day.value, works = 0, maybe = 0;
      routes.forEach(function (r) {
        var box = r.querySelector('.route-fit'); if (!box) return;
        var days = r.dataset.days ? r.dataset.days.split(',') : [], last = mins(r.dataset.last), ev = r.dataset.evening;
        var state, text;
        if (!r.dataset.fromMale) { state = 'leg'; text = 'Second leg: from ' + r.dataset.origin; }
        else if (days.length && days.indexOf(d) < 0) { state = 'no'; text = 'Doesn’t run on ' + names[d] + 's'; }
        else if (ev === 'yes') { state = 'ok'; text = 'Works: can leave after you land'; }
        else if (last !== null) {
          if (ready <= last) { state = 'ok'; text = 'Works: last one leaves ' + r.dataset.last; }
          else { state = 'no'; text = 'Too late: the last one leaves ' + r.dataset.last; }
        } else if (ev === 'no') {
          if (ready >= 17 * 60) { state = 'no'; text = 'Daytime only: too late for this landing'; }
          else { state = 'maybe'; text = 'Daytime only: probably fine, check the times'; }
        } else { state = 'maybe'; text = 'Check the departure times'; }
        if (state === 'ok') works++; if (state === 'maybe') maybe++;
        box.hidden = false; box.className = 'route-fit fit-' + state; box.textContent = text;
      });
      var island = ap.dataset.island;
      if (works) out.innerHTML = '<b>' + works + ' option' + (works > 1 ? 's' : '') + ' work' + (works > 1 ? '' : 's') + '</b> for a ' + time.value + ' landing on a ' + names[d] + '.';
      else if (maybe) out.innerHTML = '<b>Nothing confirmed for a ' + time.value + ' landing on a ' + names[d] + '.</b> Some routes have no exact times yet, so ask your host. If it’s late, a night in <a href="/islands/hulhumale/">Hulhumalé</a>, next to the airport, is the easy option.';
      else out.innerHTML = '<b>Nothing reaches ' + island + ' after a ' + time.value + ' landing on a ' + names[d] + '.</b> Many travellers spend the night in <a href="/islands/hulhumale/">Hulhumalé</a>, next to the airport, and continue in the morning. Your host can also arrange a private speedboat.';
      out.className = 'ap-out ' + (works ? 'ok' : (maybe ? 'maybe' : 'no'));
    }
    time.addEventListener('change', update); day.addEventListener('change', update); update();
  });
})();
