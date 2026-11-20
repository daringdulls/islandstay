/* Full-screen photo viewer for island and listing galleries.
 * Markup: a container with [data-lb-group="Title"] holding links a[data-lb] whose href is the large image.
 * Optional on each link: data-caption, data-credit, data-license, data-source (photo page, e.g. Wikimedia Commons).
 * Keyboard: ← → to move, G for all photos, Esc to close. Swipe on touch screens. */
(function () {
  var groups = document.querySelectorAll('[data-lb-group]');
  if (!groups.length) return;
  var box, img, counter, title, cap, credit, thumbs, grid, items = [], at = 0, lastFocus = null;

  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function icon(path) { return '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + path + '</svg>'; }

  function build() {
    box = el('div', 'lb'); box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true'); box.hidden = true;
    var top = el('div', 'lb-top');
    title = el('span', 'lb-title'); counter = el('span', 'lb-count');
    var gridBtn = el('button', 'lb-btn', icon('<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>') + '<span>All photos</span>');
    var close = el('button', 'lb-btn lb-close', icon('<path d="M18 6 6 18M6 6l12 12"/>')); close.setAttribute('aria-label', 'Close');
    gridBtn.type = close.type = 'button';
    var left = el('div', 'lb-top-l'); left.append(title, counter);
    var right = el('div', 'lb-top-r'); right.append(gridBtn, close);
    top.append(left, right);
    var stage = el('div', 'lb-stage');
    var prev = el('button', 'lb-nav lb-prev', icon('<path d="m15 18-6-6 6-6"/>')); prev.setAttribute('aria-label', 'Previous photo');
    var next = el('button', 'lb-nav lb-next', icon('<path d="m9 18 6-6-6-6"/>')); next.setAttribute('aria-label', 'Next photo');
    prev.type = next.type = 'button';
    img = el('img', 'lb-img'); img.alt = '';
    stage.append(prev, img, next);
    var foot = el('div', 'lb-foot');
    cap = el('p', 'lb-cap'); credit = el('p', 'lb-credit');
    thumbs = el('div', 'lb-thumbs');
    foot.append(cap, credit, thumbs);
    grid = el('div', 'lb-grid'); grid.hidden = true;
    box.append(top, stage, foot, grid);
    document.body.appendChild(box);

    prev.onclick = function () { go(at - 1); };
    next.onclick = function () { go(at + 1); };
    close.onclick = hide;
    gridBtn.onclick = function () { showGrid(grid.hidden); };
    stage.addEventListener('click', function (e) { if (e.target === stage) hide(); });
    document.addEventListener('keydown', function (e) {
      if (box.hidden) return;
      if (e.key === 'Escape') { if (!grid.hidden) showGrid(false); else hide(); }
      else if (e.key === 'ArrowLeft') go(at - 1);
      else if (e.key === 'ArrowRight') go(at + 1);
      else if (e.key.toLowerCase() === 'g') showGrid(grid.hidden);
    });
    var x0 = null;
    stage.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
    stage.addEventListener('touchend', function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0; x0 = null;
      if (Math.abs(dx) > 40) go(at + (dx < 0 ? 1 : -1));
    });
  }

  function showGrid(on) {
    grid.hidden = !on;
    box.classList.toggle('lb-grid-on', on);
    if (on) { var cur = grid.children[at]; if (cur) cur.focus(); }
  }

  function go(i) {
    if (!items.length) return;
    at = (i + items.length) % items.length;
    var it = items[at];
    img.classList.remove('lb-in'); void img.offsetWidth;
    img.src = it.src; img.alt = it.caption || title.textContent;
    img.classList.add('lb-in');
    counter.textContent = (at + 1) + ' / ' + items.length;
    cap.textContent = it.caption || '';
    cap.hidden = !it.caption;
    credit.innerHTML = '';
    if (it.credit || it.license) {
      credit.append('Photo: ' + [it.credit, it.license].filter(Boolean).join(' · '));
      if (it.source) { var a = el('a', null, 'Source'); a.href = it.source; a.target = '_blank'; a.rel = 'noopener'; credit.append(' · ', a); }
    }
    Array.prototype.forEach.call(thumbs.children, function (t, k) { t.classList.toggle('on', k === at); if (k === at) t.scrollIntoView({ block: 'nearest', inline: 'center' }); });
    [at + 1, at - 1].forEach(function (k) { var n = items[(k + items.length) % items.length]; if (n) { var p = new Image(); p.src = n.src; } });
  }

  function open(group, start) {
    if (!box) build();
    lastFocus = document.activeElement;
    items = Array.prototype.map.call(group.querySelectorAll('a[data-lb]'), function (a) {
      var t = a.querySelector('img');
      return { src: a.href, thumb: (t && (t.currentSrc || t.src)) || a.dataset.thumb || a.href, caption: a.dataset.caption || '',
               credit: a.dataset.credit || '', license: a.dataset.license || '', source: a.dataset.source || '' };
    });
    title.textContent = group.dataset.lbGroup || '';
    thumbs.innerHTML = ''; grid.innerHTML = '';
    items.forEach(function (it, k) {
      var b = el('button', 'lb-thumb'); b.type = 'button'; b.setAttribute('aria-label', 'Photo ' + (k + 1));
      b.style.backgroundImage = 'url("' + it.thumb + '")'; b.onclick = function () { go(k); };
      thumbs.appendChild(b);
      var g = el('button', 'lb-gitem'); g.type = 'button'; g.setAttribute('aria-label', 'Open photo ' + (k + 1));
      g.style.backgroundImage = 'url("' + it.thumb + '")'; g.onclick = function () { showGrid(false); go(k); };
      grid.appendChild(g);
    });
    thumbs.hidden = items.length < 2;
    box.querySelectorAll('.lb-nav').forEach(function (n) { n.hidden = items.length < 2; });
    box.hidden = false; document.documentElement.classList.add('lb-open');
    showGrid(false);
    go(start || 0);
    box.querySelector('.lb-close').focus();
  }

  function hide() {
    box.hidden = true; document.documentElement.classList.remove('lb-open');
    img.removeAttribute('src');
    if (lastFocus) lastFocus.focus();
  }

  groups.forEach(function (group) {
    var links = group.querySelectorAll('a[data-lb]');
    links.forEach(function (a, k) {
      a.addEventListener('click', function (e) { e.preventDefault(); open(group, k); });
    });
    group.querySelectorAll('[data-lb-open]').forEach(function (b) {
      b.addEventListener('click', function (e) { e.preventDefault(); open(group, +(b.dataset.lbOpen || 0)); if (b.dataset.lbGrid !== undefined) showGrid(true); });
    });
  });
})();
