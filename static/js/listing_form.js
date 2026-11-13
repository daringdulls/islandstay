/* Listing form (owner dashboard): type tiles, sections that follow the type, live preview,
   photo drop zones, listing strength meter, add-a-room and the section stepper. */
(function () {
  var form = document.getElementById('lf-form');
  if (!form) return;
  var $ = function (s, r) { return (r || form).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || form).querySelectorAll(s)); };

  var GROUP = {
    guesthouse: 'stay', hotel: 'stay', resort: 'stay', villa: 'stay',
    activity: 'experience', dive: 'experience', other: 'experience',
    transfer: 'transport', restaurant: 'food', cafe: 'food', hut: 'food', food_truck: 'food',
    shop: 'shop', souvenir: 'shop'
  };

  function kindInput() { return $('input[name=kind]:checked'); }
  function kindGroup() { var k = kindInput(); return k ? GROUP[k.value] : ''; }

  /* ---------- sections follow the type ---------- */
  function applyKind() {
    var g = kindGroup();
    $$('[data-kinds]', document).forEach(function (el) {
      var show = !!g && el.getAttribute('data-kinds').split(' ').indexOf(g) >= 0;
      el.hidden = !show;
    });
    // renumber visible steps and section badges
    var n = 0;
    $$('.lf-steps li', document).forEach(function (li) {
      if (li.hidden) return;
      n += 1;
      li.querySelector('b').textContent = n;
      var id = li.querySelector('a').getAttribute('data-step');
      var num = document.querySelector('#' + id + ' .lf-num');
      if (num) num.textContent = n;
    });
    var k = kindInput();
    if (k) {
      var lab = k.closest('.lf-kind');
      var pv = document.getElementById('pv-kind');
      pv.querySelector('svg').outerHTML = lab.querySelector('.lf-kind-ic svg').outerHTML;
      pv.querySelector('em').textContent = lab.querySelector('.lf-kind-txt').textContent;
      pv.classList.add('on');
    }
  }
  $$('input[name=kind]').forEach(function (r) { r.addEventListener('change', function () { $('#s-type').classList.remove('has-err'); applyKind(); update(); }); });

  /* ---------- live preview ---------- */
  function text(id, value, fallback) {
    var el = document.getElementById(id);
    el.textContent = value || fallback;
    el.classList.toggle('ph', !value);
  }
  function preview() {
    var name = $('[name=name]'), island = $('[name=island]'), short = $('[name=short_description]');
    text('pv-name', name && name.value.trim(), 'Your business name');
    var isl = island && island.selectedIndex > 0 ? island.options[island.selectedIndex].text : '';
    text('pv-island', isl.replace(' — ', ', '), 'Choose your island');
    text('pv-desc', short && short.value.trim(), 'Your headline appears here.');
    var tags = document.getElementById('pv-tags');
    var picked = $$('.lf-chip input:checked').filter(function (c) { return !c.closest('[data-kinds]') || !c.closest('[data-kinds]').hidden; });
    tags.innerHTML = '';
    picked.slice(0, 4).forEach(function (c) {
      var s = document.createElement('span');
      s.textContent = c.parentNode.querySelector('span').textContent.trim();
      tags.appendChild(s);
    });
    if (picked.length > 4) { var more = document.createElement('span'); more.textContent = '+' + (picked.length - 4); tags.appendChild(more); }
  }

  /* ---------- character counters ---------- */
  $$('[data-count-for]', document).forEach(function (c) {
    var input = document.getElementById(c.getAttribute('data-count-for'));
    if (!input) return;
    var max = parseInt(input.getAttribute('maxlength') || '200', 10);
    function count() { c.textContent = input.value.length + ' / ' + max; c.classList.toggle('near', input.value.length > max * 0.9); }
    input.addEventListener('input', count); count();
  });

  /* ---------- photo drop zones ---------- */
  $$('.lf-drop').forEach(function (drop) {
    var input = drop.querySelector('input[type=file]'), img = drop.querySelector('.lf-drop-img');
    var target = document.getElementById(drop.getAttribute('data-preview') === 'cover' ? 'pv-cover' : 'pv-logo');
    if (img.style.backgroundImage) drop.classList.add('has');
    function show(file) {
      if (!file || !/^image\//.test(file.type)) return;
      var url = URL.createObjectURL(file);
      img.style.backgroundImage = target.style.backgroundImage = 'url("' + url + '")';
      drop.classList.add('has');
      update();
    }
    input.addEventListener('change', function () { show(input.files[0]); });
    ['dragenter', 'dragover'].forEach(function (e) { drop.addEventListener(e, function (ev) { ev.preventDefault(); drop.classList.add('over'); }); });
    ['dragleave', 'drop'].forEach(function (e) { drop.addEventListener(e, function () { drop.classList.remove('over'); }); });
    drop.addEventListener('drop', function (ev) {
      ev.preventDefault();
      if (!ev.dataTransfer.files.length) return;
      try { input.files = ev.dataTransfer.files; } catch (e) { /* older browsers: preview only */ }
      show(ev.dataTransfer.files[0]);
    });
  });

  /* ---------- rooms: add another ---------- */
  var addBtn = document.getElementById('lf-add-room'), tpl = document.getElementById('lf-room-tpl');
  var total = $('[name=rooms-TOTAL_FORMS]');
  if (addBtn && tpl && total) {
    addBtn.addEventListener('click', function () {
      var i = parseInt(total.value, 10);
      var html = tpl.innerHTML.replace(/__prefix__/g, i).replace(/__n__/g, i + 1);
      var wrap = document.createElement('div'); wrap.innerHTML = html.trim();
      var room = wrap.firstChild;
      document.getElementById('lf-rooms').appendChild(room);
      total.value = i + 1;
      room.classList.add('new');
      var first = room.querySelector('input[type=text]'); if (first) first.focus();
    });
  }

  /* ---------- listing strength ---------- */
  function val(name) { var el = $('[name=' + name + ']'); return el && el.value && el.value.trim(); }
  function hasPhoto(which) { var d = $('.lf-drop-' + which); return d && d.classList.contains('has'); }
  function update() {
    preview();
    var g = kindGroup();
    var checks = [
      [!!kindInput(), 'Choose what you offer', 's-type'],
      [!!val('name'), 'Add your business name', 's-about'],
      [!!val('island'), 'Choose your island', 's-about'],
      [(val('short_description') || '').length >= 20, 'Write a one-line headline', 's-about'],
      [(val('description') || '').length >= 120, 'Write a fuller description (a few sentences)', 's-about'],
      [hasPhoto('cover'), 'Add a cover photo', 's-photos'],
      [!!val('contact_name') && !!val('contact_email'), 'Add your name and email', 's-contact'],
      [!!(val('whatsapp') || val('contact_phone')), 'Add a phone or WhatsApp number', 's-contact']
    ];
    if (g === 'stay') {
      checks.push([$$('#s-stay .lf-chip input:checked').length >= 3, 'Tick at least 3 facilities', 's-stay']);
      checks.push([!!val('rooms-0-name'), 'Add your first room type', 's-rooms']);
    }
    if (g === 'experience') checks.push([$$('#s-exp .lf-chip input:checked').length >= 1, 'Pick the experiences you offer', 's-exp']);
    if (g === 'food') checks.push([!!val('opening_hours'), 'Add your opening hours', 's-food']);
    var done = checks.filter(function (c) { return c[0]; }).length;
    var pct = Math.round(done / checks.length * 100);
    document.getElementById('lf-pct').textContent = pct + '%';
    document.getElementById('lf-pct-m').textContent = pct + '%';
    var bar = document.getElementById('lf-bar');
    bar.style.width = pct + '%';
    bar.className = pct >= 100 ? 'full' : pct >= 60 ? 'good' : '';
    var todo = document.getElementById('lf-todo');
    todo.innerHTML = '';
    checks.filter(function (c) { return !c[0]; }).slice(0, 3).forEach(function (c) {
      var li = document.createElement('li'), a = document.createElement('a');
      a.href = '#' + c[2]; a.textContent = c[1]; li.appendChild(a); todo.appendChild(li);
    });
    if (pct === 100) todo.innerHTML = '<li class="ok">Looking great. Ready to submit.</li>';
  }
  form.addEventListener('input', update);
  form.addEventListener('change', update);

  /* ---------- stepper follows the scroll ---------- */
  var links = $$('.lf-steps a');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (a) { a.classList.toggle('on', a.getAttribute('data-step') === e.target.id); });
      });
    }, { rootMargin: '-35% 0px -55% 0px' });
    $$('.lf-card[id]').forEach(function (s) { io.observe(s); });
  }

  /* ---------- friendly check before submitting ---------- */
  form.addEventListener('submit', function (ev) {
    var missing = null;
    if (!kindInput()) missing = $('#s-type');
    else $$('[required]').some(function (el) {
      if (el.closest('[hidden]') || el.type === 'radio') return false;
      if (!el.value.trim()) { missing = el; return true; }
      return false;
    });
    if (!missing) return;
    ev.preventDefault();
    var box = missing.closest('.lf-f') || missing;
    box.classList.add('has-err', 'shake');
    setTimeout(function () { box.classList.remove('shake'); }, 600);
    box.scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (missing.focus) setTimeout(function () { missing.focus({ preventScroll: true }); }, 350);
  });
  form.addEventListener('input', function (ev) {
    var f = ev.target.closest && ev.target.closest('.lf-f.has-err');
    if (f && ev.target.value) f.classList.remove('has-err');
  });

  applyKind();
  update();
})();
