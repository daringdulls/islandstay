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
