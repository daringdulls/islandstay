/* Phone photos are often 3–12 MB, but the site's server accepts at most about 4.5 MB per request.
 * Before any form with a file upload is sent, large photos are resized in the browser (longest side 2400 px,
 * JPEG 85%), which keeps them sharp on screen and usually brings each one under 1 MB. If the upload is still
 * too big (for example a large PDF), a clear message is shown instead of the server's error page.
 * Used on the public site and in the back office. */
(function () {
  var LIMIT = 4 * 1024 * 1024;        // stay safely below the 4.5 MB request limit
  var SKIP_BELOW = 900 * 1024;         // small images are sent as they are

  function mb(n) { return (n / 1048576).toFixed(1) + ' MB'; }

  function decode(file) {
    if (window.createImageBitmap) {
      return createImageBitmap(file, { imageOrientation: 'from-image' }).catch(function () { return viaImg(file); });
    }
    return viaImg(file);
  }
  function viaImg(file) {
    return new Promise(function (resolve, reject) {
      var img = new Image(), url = URL.createObjectURL(file);
      img.onload = function () { resolve(img); };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('unreadable')); };
      img.src = url;
    });
  }

  async function shrink(file, maxSide, quality) {
    if (!/^image\//.test(file.type) || file.type === 'image/gif' || file.type === 'image/svg+xml') return file;
    var src;
    try { src = await decode(file); } catch (e) { return file; }
    var w = src.width, h = src.height, k = Math.min(1, maxSide / Math.max(w, h));
    var c = document.createElement('canvas');
    c.width = Math.round(w * k); c.height = Math.round(h * k);
    var g = c.getContext('2d');
    var keepPng = file.type === 'image/png' && file.size < 3 * 1048576;   // logos with transparency stay PNG
    if (!keepPng) { g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); }
    g.drawImage(src, 0, 0, c.width, c.height);
    if (src.close) src.close();
    var type = keepPng ? 'image/png' : 'image/jpeg';
    var blob = await new Promise(function (r) { c.toBlob(r, type, quality); });
    if (!blob || blob.size >= file.size) return file;
    var name = keepPng ? file.name : file.name.replace(/\.[a-z0-9]+$/i, '') + '.jpg';
    return new File([blob], name, { type: type, lastModified: Date.now() });
  }

  function inputsOf(form) {
    return Array.prototype.slice.call(form.querySelectorAll('input[type=file]')).filter(function (i) { return i.files && i.files.length; });
  }
  function total(form) {
    return inputsOf(form).reduce(function (n, i) { return n + Array.prototype.reduce.call(i.files, function (m, f) { return m + f.size; }, 0); }, 0);
  }

  async function prepare(form, maxSide, quality, minSize) {
    for (var input of inputsOf(form)) {
      var dt = new DataTransfer(), changed = false;
      for (var f of Array.prototype.slice.call(input.files)) {
        var out = f.size > minSize ? await shrink(f, maxSide, quality) : f;
        if (out !== f) changed = true;
        dt.items.add(out);
      }
      if (changed) input.files = dt.files;
    }
  }

  function notice(form, text) {
    var box = form.querySelector('.upload-note');
    if (!box) {
      box = document.createElement('p');
      box.className = 'upload-note';
      box.setAttribute('role', 'alert');
      box.style.cssText = 'margin:12px 0;padding:10px 14px;border-radius:12px;background:#fdf0ec;border:1px solid #f1c6b9;color:#B9442C;font-size:.9rem';
      var btn = form.querySelector('[type=submit]');
      (btn ? btn.parentNode : form).insertBefore(box, btn || null);
    }
    box.textContent = text;
    box.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function busy(submitter, on) {
    if (!submitter) return;
    if (on) { submitter.dataset.label = submitter.innerHTML; submitter.disabled = true; submitter.textContent = 'Preparing photos…'; }
    else if (submitter.dataset.label) { submitter.innerHTML = submitter.dataset.label; submitter.disabled = false; }
  }

  window.addEventListener('submit', async function (ev) {
    var form = ev.target;
    if (!(form instanceof HTMLFormElement) || (form.enctype || '').indexOf('multipart') < 0) return;
    if (form.dataset.uploadReady === '1') { delete form.dataset.uploadReady; return; }
    var files = inputsOf(form);
    if (!files.length || !window.DataTransfer) return;
    var needs = total(form) > LIMIT || files.some(function (i) {
      return Array.prototype.some.call(i.files, function (f) { return /^image\//.test(f.type) && f.size > SKIP_BELOW; });
    });
    if (!needs) return;
    // Hold the form, shrink the photos, then send it again (other checks on the form run then).
    ev.preventDefault();
    ev.stopPropagation();
    var submitter = ev.submitter;
    busy(submitter, true);
    try {
      await prepare(form, 2400, 0.85, SKIP_BELOW);
      if (total(form) > LIMIT) await prepare(form, 1600, 0.75, 0);   // many photos at once: a bit smaller still
    } catch (e) { /* send what we have; the size check below still applies */ }
    busy(submitter, false);
    var size = total(form);
    if (size > LIMIT) {
      var many = files.some(function (i) { return i.files.length > 1; });
      notice(form, many
        ? 'These files are too large to send together (' + mb(size) + '). Please choose fewer photos at a time.'
        : 'This file is too large to upload (' + mb(size) + '). Please choose a file under 4 MB, for example a photo of the document instead of a scan.');
      return;
    }
    var old = form.querySelector('.upload-note'); if (old) old.remove();
    form.dataset.uploadReady = '1';
    if (form.requestSubmit) form.requestSubmit(submitter && submitter.form === form ? submitter : undefined);
    else form.submit();
  }, true);
})();
