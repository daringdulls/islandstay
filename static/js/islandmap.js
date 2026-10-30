/* IslandStay interactive map (Leaflet).
 *
 * <div data-island-map data-mode="explore|focus" data-focus-island="slug" data-focus-atoll="slug"
 *      data-source="map-data" data-panel="#map-panel"></div>
 * Data comes from a json_script block: {atolls: [{slug, name, shape: [lat, lng, rlat, rlng], ...}],
 * islands: [{slug, name, atoll, lat, lng, photo, ...}]}. Elements with [data-atoll-link="slug"] anywhere
 * on the page highlight and select that atoll.
 */
(function () {
  "use strict";
  if (!window.L) return;

  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var config = JSON.parse((document.getElementById("map-config") || {}).textContent || "{}");

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function ellipse(shape) {
    var pts = [], lat = shape[0], lng = shape[1], rl = shape[2], rg = shape[3];
    for (var i = 0; i < 48; i++) {
      var a = (i / 48) * Math.PI * 2;
      // a slightly irregular outline reads more like a reef than a perfect oval
      var wobble = 1 + 0.06 * Math.sin(a * 3 + lat) + 0.04 * Math.cos(a * 5 + lng);
      pts.push([lat + Math.sin(a) * rl * wobble, lng + Math.cos(a) * rg * wobble]);
    }
    return pts;
  }

  var STYLE = {
    base: { color: "#0a3d4c", weight: 1.4, opacity: 0.7, dashArray: "4 5", fillColor: "#4cc3c7", fillOpacity: 0.12 },
    hover: { weight: 2, opacity: 1, dashArray: null, fillOpacity: 0.22 },
    active: { color: "#0b6e8a", weight: 2.5, opacity: 1, dashArray: null, fillOpacity: 0.32 },
  };

  function popupHtml(i) {
    var chips = [];
    if (i.population) chips.push("Pop. " + Number(i.population).toLocaleString());
    if (i.transfer) chips.push(esc(i.transfer));
    if (i.bikini) chips.push("Bikini beach");
    return '<a class="map-card" href="' + esc(i.url) + '">' +
      (i.photo ? '<img src="' + esc(i.photo) + '" alt="" loading="lazy">' : '<span class="map-card-chart"></span>') +
      '<span class="map-card-body"><small>' + esc(i.atollName) + "</small><b>" + esc(i.name) + "</b>" +
      "<span>" + esc(i.tagline) + "</span>" +
      '<span class="map-card-chips">' + chips.map(function (c) { return "<em>" + c + "</em>"; }).join("") + "</span>" +
      '<span class="map-card-foot">' + i.stays + " stay" + (i.stays === 1 ? "" : "s") + " · " + i.experiences +
      " experience" + (i.experiences === 1 ? "" : "s") + '<strong>Open guide →</strong></span></span></a>';
  }

  function init(el) {
    var data = JSON.parse(document.getElementById(el.dataset.source || "map-data").textContent);
    var mode = el.dataset.mode || "explore";
    var panel = el.dataset.panel ? document.querySelector(el.dataset.panel) : null;

    var map = L.map(el, {
      zoomControl: false, scrollWheelZoom: false, attributionControl: true,
      minZoom: 4, maxZoom: 16, zoomSnap: 0.25, worldCopyJump: false,
    });
    L.control.zoom({ position: "bottomright" }).addTo(map);
    if (config.tiles) {
      L.tileLayer(config.tiles, { attribution: config.attribution, maxZoom: 19, className: "map-tiles" }).addTo(map);
    }
    // Wheel-zoom only after the visitor engages with the map, so the page still scrolls normally.
    map.on("click focus", function () { map.scrollWheelZoom.enable(); });
    el.addEventListener("mouseleave", function () { map.scrollWheelZoom.disable(); });

    var atollLayers = {}, islandMarkers = {}, active = null;
    var all = L.featureGroup();

    data.atolls.forEach(function (a) {
      var poly = L.polygon(ellipse(a.shape), STYLE.base).addTo(map);
      poly.bindTooltip(a.name, { permanent: true, direction: "center", className: "atoll-label", interactive: false });
      poly.on("mouseover", function () { hover(a.slug, true); });
      poly.on("mouseout", function () { hover(a.slug, false); });
      poly.on("click", function () { select(a.slug); });
      atollLayers[a.slug] = poly;
      all.addLayer(poly);
    });

    data.islands.forEach(function (i, n) {
      var cls = "pin" + (i.featured ? " pin-featured" : "") + (i.slug === el.dataset.focusIsland ? " pin-current" : "");
      var icon = L.divIcon({
        className: "pin-wrap",
        html: '<span class="' + cls + '" style="animation-delay:' + (reduceMotion ? 0 : 1.6 + n * 0.05) + 's"><i></i></span>' +
          '<span class="pin-name">' + esc(i.name) + "</span>",
        iconSize: [18, 18], iconAnchor: [9, 9], popupAnchor: [0, -10],
      });
      var m = L.marker([i.lat, i.lng], { icon: icon, title: i.name, riseOnHover: true }).addTo(map);
      m.bindPopup(popupHtml(i), {
        className: "map-popup", maxWidth: 300, minWidth: 260, closeButton: true,
        // keep the card clear of the atoll panel on the right
        autoPanPaddingTopLeft: L.point(16, 16), autoPanPaddingBottomRight: L.point(panel && window.innerWidth > 600 ? 360 : 16, 16),
      });
      islandMarkers[i.slug] = m;
      all.addLayer(m);
    });

    function setZoomClass() {
      var z = map.getZoom();
      el.classList.toggle("z-far", z < 6.25);
      el.classList.toggle("z-near", z >= 7.5);
    }
    map.on("zoomend", setZoomClass);

    function listItems(slug) {
      return document.querySelectorAll('[data-atoll-link="' + slug + '"]');
    }

    function hover(slug, on) {
      var layer = atollLayers[slug];
      if (layer && slug !== active) layer.setStyle(on ? STYLE.hover : STYLE.base);
      listItems(slug).forEach(function (li) { li.classList.toggle("is-hover", on); });
    }

    function renderPanel(a) {
      if (!panel) return;
      var islands = data.islands.filter(function (i) { return i.atoll === a.slug; });
      panel.innerHTML =
        '<div class="map-panel-head"><small>' + esc(a.official) + (a.code ? " · " + esc(a.code) : "") + "</small>" +
        "<h3>" + esc(a.name) + "</h3><p>" + esc(a.description) + "</p></div>" +
        (islands.length
          ? '<ul class="map-panel-list">' + islands.map(function (i) {
              return '<li><button type="button" data-fly="' + esc(i.slug) + '"><span>' + esc(i.name) +
                "</span><small>" + esc(i.tagline) + "</small></button></li>";
            }).join("") + "</ul>"
          : '<p class="map-panel-empty">No island guides here yet.</p>') +
        '<div class="map-panel-foot"><a class="btn btn-sm" href="' + esc(a.url) + '">Open atoll guide</a>' +
        '<button type="button" class="btn btn-ghost btn-sm" data-reset>Whole country</button></div>';
      panel.classList.add("is-open");
    }

    function select(slug) {
      var a = data.atolls.filter(function (x) { return x.slug === slug; })[0];
      if (!a) return;
      if (active && atollLayers[active]) atollLayers[active].setStyle(STYLE.base);
      document.querySelectorAll("[data-atoll-link].is-active").forEach(function (li) { li.classList.remove("is-active"); });
      active = slug;
      atollLayers[slug].setStyle(STYLE.active);
      listItems(slug).forEach(function (li) { li.classList.add("is-active"); });
      var bounds = atollLayers[slug].getBounds().pad(0.35);
      reduceMotion ? map.fitBounds(bounds) : map.flyToBounds(bounds, { duration: 1.1 });
      renderPanel(a);
    }

    function fly(slug) {
      var m = islandMarkers[slug];
      if (!m) return;
      var go = function () { m.openPopup(); };
      if (reduceMotion) { map.setView(m.getLatLng(), 11); go(); }
      else { map.once("moveend", go); map.flyTo(m.getLatLng(), 11, { duration: 1.1 }); }
    }

    function reset() {
      if (active && atollLayers[active]) atollLayers[active].setStyle(STYLE.base);
      document.querySelectorAll("[data-atoll-link].is-active").forEach(function (li) { li.classList.remove("is-active"); });
      active = null;
      map.closePopup();
      if (panel) panel.classList.remove("is-open");
      reduceMotion ? map.fitBounds(all.getBounds().pad(0.05)) : map.flyToBounds(all.getBounds().pad(0.05), { duration: 1.2 });
    }

    // Links elsewhere on the page (the atoll index) drive the map.
    document.querySelectorAll("[data-atoll-link]").forEach(function (li) {
      var slug = li.getAttribute("data-atoll-link");
      li.addEventListener("mouseenter", function () { hover(slug, true); });
      li.addEventListener("mouseleave", function () { hover(slug, false); });
      li.addEventListener("click", function (e) {
        if (mode !== "explore") return;
        e.preventDefault();
        select(slug);
        var r = el.getBoundingClientRect();
        if (r.top < 0 || r.top > window.innerHeight * 0.6) {
          el.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
        }
      });
    });
    if (panel) {
      panel.addEventListener("click", function (e) {
        var t = e.target.closest("[data-fly],[data-reset]");
        if (!t) return;
        if (t.hasAttribute("data-reset")) reset(); else fly(t.getAttribute("data-fly"));
      });
    }

    // Initial view: fly in from the Indian Ocean on the home page; focus pages start close.
    if (mode === "focus" && el.dataset.focusIsland && islandMarkers[el.dataset.focusIsland]) {
      map.setView(islandMarkers[el.dataset.focusIsland].getLatLng(), 10);
      if (el.dataset.focusAtoll && atollLayers[el.dataset.focusAtoll]) atollLayers[el.dataset.focusAtoll].setStyle(STYLE.active);
    } else if (mode === "focus" && el.dataset.focusAtoll && atollLayers[el.dataset.focusAtoll]) {
      atollLayers[el.dataset.focusAtoll].setStyle(STYLE.active);
      map.fitBounds(atollLayers[el.dataset.focusAtoll].getBounds().pad(0.2));
    } else {
      var target = all.getBounds().pad(0.05);
      if (reduceMotion) map.fitBounds(target);
      else {
        map.setView([3.2, 76.5], 4.5);
        setTimeout(function () { map.flyToBounds(target, { duration: 2.2, easeLinearity: 0.2 }); }, 350);
      }
    }
    setZoomClass();
    el.classList.add("map-ready");
    return { map: map, select: select, fly: fly, reset: reset };
  }

  document.querySelectorAll("[data-island-map]").forEach(function (el) {
    try { el._islandMap = init(el); } catch (err) { console.error("Map failed to load", err); }
  });
})();
