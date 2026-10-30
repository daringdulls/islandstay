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
