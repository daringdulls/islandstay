/* Instant photo manager for islands and listings: every change is saved straight away. */
(function () {
  "use strict";
  var root = document.getElementById("pm");
  if (!root) return;
  var kind = root.dataset.kind, url = root.dataset.url;
  var state = JSON.parse(document.getElementById("pm-state").textContent);
  var statusEl = document.getElementById("pm-status"), gallery = document.getElementById("pm-gallery");
  var one = document.getElementById("pm-file-one"), many = document.getElementById("pm-file-many");
  var pendingSlot = null;

  function csrf() { var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/); var i = document.querySelector("input[name=csrfmiddlewaretoken]"); return (i && i.value) || (m && decodeURIComponent(m[1])) || ""; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function status(text, kindClass) { statusEl.textContent = text || ""; statusEl.className = "pm-status " + (kindClass || ""); if (kindClass === "ok") setTimeout(function () { if (statusEl.textContent === text) status(""); }, 2500); }

  // Shrink big photos in the browser before uploading (keeps PNG logos as PNG).
  function resize(file, maxSide, keepPng) {
    return new Promise(function (resolve) {
      if (!/^image\/(jpeg|png|webp)$/.test(file.type) || file.size < 400 * 1024 && !keepPng) { resolve(file); return; }
      var img = new Image(), u = URL.createObjectURL(file);
      img.onload = function () {
        URL.revokeObjectURL(u);
        var scale = Math.min(1, maxSide / Math.max(img.width, img.height));
        if (scale === 1 && file.size < 1.5 * 1024 * 1024) { resolve(file); return; }
        var c = document.createElement("canvas"); c.width = Math.round(img.width * scale); c.height = Math.round(img.height * scale);
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        var png = keepPng && file.type === "image/png", type = png ? "image/png" : "image/jpeg";
        c.toBlob(function (b) {
          if (!b || b.size >= file.size) { resolve(file); return; }
          resolve(new File([b], file.name.replace(/\.\w+$/, "") + (png ? ".png" : ".jpg"), { type: type }));
        }, type, 0.85);
      };
      img.onerror = function () { URL.revokeObjectURL(u); resolve(file); };
      img.src = u;
    });
  }

  function send(action, data, files, fileField) {
    var fd = new FormData(); fd.append("action", action);
    Object.keys(data || {}).forEach(function (k) { fd.append(k, data[k]); });
    (files || []).forEach(function (f) { fd.append(fileField || "file", f); });
    root.classList.add("busy");
    return fetch(url, { method: "POST", body: fd, credentials: "same-origin", headers: { "X-CSRFToken": csrf() } })
      .then(function (r) { return r.json().catch(function () { return { error: "The server didn't answer (" + r.status + ")." }; }); })
      .then(function (d) {
        root.classList.remove("busy");
        if (d.error) { status(d.error, "err"); throw new Error(d.error); }
        state = d.state; render();
        if (d.errors && d.errors.length) status(d.errors.join(" · "), "err"); else status("Saved", "ok");
        return d;
      }, function (e) { root.classList.remove("busy"); status("Couldn't reach the server. Check your connection.", "err"); throw e; });
  }

  // ---------------------------------------------------------------- slots (cover and logo)
  function slotHtml(slot) {
    var img = slot === "cover" ? state.cover : state.logo;
    var fallback = slot === "cover" && !img && state.fallback;
    if (img) {
      return '<div class="pm-img ' + slot + '"><img src="' + esc(img) + '" alt="" onerror="this.parentNode.classList.add(\'missing\')"><span class="pm-missing"><span class="material-symbols-outlined">broken_image</span>Photo file missing — replace or remove</span>' +
        '<div class="pm-img-actions"><button type="button" data-pick="' + slot + '"><span class="material-symbols-outlined">upload</span>Replace</button>' +
        '<button type="button" class="danger" data-remove="' + slot + '"><span class="material-symbols-outlined">delete</span>Remove</button></div></div>' +
        (slot === "cover" && kind === "island" ? '<label class="pm-credit">Photo credit <input type="text" value="' + esc(state.cover_credit) + '" data-credit placeholder="e.g. Photo: Aishath Ali"></label>' : "");
    }
    return '<button type="button" class="pm-empty ' + slot + '" data-pick="' + slot + '">' + (fallback ? '<img src="' + esc(fallback) + '" alt="">' : "") +
      '<span class="material-symbols-outlined">add_photo_alternate</span><b>' + (slot === "cover" ? "Add a cover photo" : "Add a logo") + "</b>" +
      "<small>Click or drop a photo here" + (fallback ? " · the island photo is shown until you add one" : "") + "</small></button>" +
      (slot === "cover" && kind === "island" ? '<div class="pm-linkrow"><input type="text" placeholder="…or paste a photo link (https://…)" data-link><button type="button" data-use-link>Use link</button></div>' : "");
  }
  function render() {
    root.querySelectorAll("[data-drop]").forEach(function (d) { d.innerHTML = slotHtml(d.dataset.drop); });
    var g = state.gallery || [];
    document.getElementById("pm-count").textContent = g.length ? g.length + " photo" + (g.length === 1 ? "" : "s") : "";
    gallery.innerHTML = g.map(function (p) {
      return '<figure class="pm-tile' + (p.is_cover ? " is-cover" : "") + (p.visible === false ? " hidden-photo" : "") + '" draggable="true" data-id="' + p.id + '">' +
        '<img src="' + esc(p.url) + '" alt="" loading="lazy" onerror="this.parentNode.classList.add(\'missing\')"><span class="pm-missing"><span class="material-symbols-outlined">broken_image</span>File missing</span>' +
        (p.is_cover ? '<span class="pm-badge">Cover</span>' : "") +
        '<div class="pm-tile-actions">' +
        (p.is_cover ? "" : '<button type="button" title="Make this the cover photo" data-cover="' + p.id + '"><span class="material-symbols-outlined">star</span></button>') +
        (kind === "island" ? '<button type="button" title="' + (p.visible === false ? "Show on the site" : "Hide from the site") + '" data-visible="' + p.id + '"><span class="material-symbols-outlined">' + (p.visible === false ? "visibility_off" : "visibility") + "</span></button>" : "") +
        '<button type="button" class="danger" title="Delete this photo" data-del="' + p.id + '"><span class="material-symbols-outlined">close</span></button></div>' +
        '<input type="text" value="' + esc(p.caption) + '" placeholder="Add a caption" data-caption="' + p.id + '"></figure>';
    }).join("") + '<button type="button" class="pm-add" data-pick="gallery"><span class="material-symbols-outlined">add</span><b>Add photos</b><small>Choose several at once, or drop them here</small></button>';
  }

  // ---------------------------------------------------------------- uploads
  function upload(slot, fileList) {
    var files = Array.prototype.slice.call(fileList || []).filter(function (f) { return /^image\//.test(f.type); });
    if (!files.length) { status("Choose a photo file (JPG, PNG or WebP).", "err"); return; }
    status(files.length > 1 ? "Uploading " + files.length + " photos…" : "Uploading…", "busy");
    var max = slot === "logo" ? 800 : 2400;
    Promise.all(files.map(function (f) { return resize(f, max, slot === "logo"); })).then(function (ready) {
      if (slot === "gallery") {
        // send in small batches so one request never gets too big
        var batches = []; for (var i = 0; i < ready.length; i += 4) batches.push(ready.slice(i, i + 4));
        return batches.reduce(function (p, b, n) {
          return p.then(function () { status("Uploading " + Math.min((n + 1) * 4, ready.length) + " of " + ready.length + "…", "busy"); return send("gallery_upload", { auto_cover: state.cover ? "0" : "1" }, b, "files"); });
        }, Promise.resolve());
      }
      return send(slot + "_upload", {}, [ready[0]]);
    }).catch(function () {});
  }
  root.addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    if (b.dataset.pick) { pendingSlot = b.dataset.pick; (pendingSlot === "gallery" ? many : one).click(); }
    else if (b.dataset.remove) { if (confirm("Remove the " + b.dataset.remove + "?")) send(b.dataset.remove + "_remove").catch(function () {}); }
    else if (b.dataset.cover) send("gallery_cover", { id: b.dataset.cover }).catch(function () {});
    else if (b.dataset.del) { if (confirm("Delete this photo?")) send("gallery_delete", { id: b.dataset.del }).catch(function () {}); }
    else if (b.dataset.visible) { var p = state.gallery.find(function (x) { return String(x.id) === b.dataset.visible; }); send("gallery_visible", { id: b.dataset.visible, visible: p.visible === false ? "1" : "0" }).catch(function () {}); }
    else if (b.hasAttribute("data-use-link")) { var inp = root.querySelector("[data-link]"); send("cover_link", { url: inp.value.trim() }).catch(function () {}); }
  });
  one.addEventListener("change", function () { upload(pendingSlot, one.files); one.value = ""; });
  many.addEventListener("change", function () { upload("gallery", many.files); many.value = ""; });
  root.addEventListener("change", function (e) {
    var t = e.target;
    if (t.dataset.caption) send("gallery_caption", { id: t.dataset.caption, caption: t.value }).catch(function () {});
    if (t.hasAttribute("data-credit")) send("cover_credit", { credit: t.value }).catch(function () {});
  });
  root.addEventListener("keydown", function (e) { if (e.key === "Enter" && e.target.tagName === "INPUT") { e.preventDefault(); e.target.blur(); } });

  // ---------------------------------------------------------------- drag and drop: files from the computer, and reordering
  var dragTile = null;
  root.addEventListener("dragstart", function (e) { var t = e.target.closest(".pm-tile"); if (t) { dragTile = t; t.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; } });
  root.addEventListener("dragend", function () { if (dragTile) dragTile.classList.remove("dragging"); dragTile = null; root.querySelectorAll(".over").forEach(function (n) { n.classList.remove("over"); }); });
  root.addEventListener("dragover", function (e) {
    e.preventDefault();
    root.querySelectorAll(".over").forEach(function (n) { n.classList.remove("over"); });
    var target = dragTile ? e.target.closest(".pm-tile") : (e.target.closest("[data-drop]") || e.target.closest(".pm-gallery"));
    if (target && target !== dragTile) target.classList.add("over");
  });
  root.addEventListener("drop", function (e) {
    e.preventDefault();
    root.querySelectorAll(".over").forEach(function (n) { n.classList.remove("over"); });
    if (dragTile) {
      var over = e.target.closest(".pm-tile");
      if (over && over !== dragTile) {
        var tiles = Array.prototype.slice.call(gallery.querySelectorAll(".pm-tile"));
        if (tiles.indexOf(dragTile) < tiles.indexOf(over)) over.after(dragTile); else over.before(dragTile);
        var ids = Array.prototype.map.call(gallery.querySelectorAll(".pm-tile"), function (t) { return +t.dataset.id; });
        send("gallery_order", { ids: JSON.stringify(ids) }).catch(function () {});
      }
      return;
    }
    if (!e.dataTransfer || !e.dataTransfer.files.length) return;
    var slot = e.target.closest("[data-drop]");
    upload(slot ? slot.dataset.drop : "gallery", e.dataTransfer.files);
  });

  render();
})();
