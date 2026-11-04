/* Island Stay guide editor: content blocks, block library, live preview and publishing checklist. */
(function () {
  "use strict";
  var root = document.getElementById("ge");
  if (!root) return;
  var DATA = JSON.parse(document.getElementById("ge-data").textContent);
  var TPLS = DATA.templates, ISLANDS = DATA.islands, PICK = DATA.pick;
  var csrf = DATA.csrf;

  // ------------------------------------------------------------------ block types
  var F = {
    url: { k: "url", t: "image", label: "Photo" },
    caption: { k: "caption", t: "text", label: "Caption", ph: "What's in the photo" },
    credit: { k: "credit", t: "text", label: "Photo credit", ph: "e.g. Aishath Ali" },
    alt: { k: "alt", t: "text", label: "Describe the photo", help: "Read out to blind visitors and used by Google." },
    title: { k: "title", t: "text", label: "Title" },
    note: { k: "note", t: "textarea", label: "Short note (optional)", rows: 2 },
  };
  var TEXT_HELP = "Empty line between paragraphs · '- ' for a bullet · **bold** · [link text](/islands/maafushi/)";
  var BLOCKS = {
    rich_text: { label: "Rich text", icon: "notes", group: "Text", desc: "Paragraphs, bullet points, bold and links.", fields: [{ k: "text", t: "textarea", label: "Text", rows: 8, help: TEXT_HELP }] },
    heading: { label: "Heading & section intro", icon: "title", group: "Text", desc: "A new section, shown in “In this guide”.", fields: [{ k: "title", t: "text", label: "Heading" }, { k: "intro", t: "textarea", label: "Intro (optional)", rows: 2 }] },
    quote: { label: "Editorial pull quote", icon: "format_quote", group: "Text", desc: "A big quote from a host, guest or local.", fields: [{ k: "quote", t: "textarea", label: "Quote", rows: 3 }, { k: "author", t: "text", label: "Who said it", ph: "e.g. Ibrahim, boat captain on Dhigurah" }] },
    facts: { label: "Guide box / fast facts", icon: "fact_check", group: "Text", desc: "Key facts in a box: time, price, season…", fields: [{ k: "title", t: "text", label: "Box title", ph: "Fast facts" }, { k: "items", t: "facts" }, F.note] },
    image: { label: "Single image", icon: "image", group: "Media", desc: "One photo with caption and credit.", fields: [F.url, F.caption, F.credit, F.alt] },
    hero_image: { label: "Full-width bleed hero image", icon: "panorama", group: "Media", desc: "A photo across the whole screen.", fields: [F.url, F.caption, F.credit, F.alt] },
    gallery: { label: "Image gallery", icon: "photo_library", group: "Media", desc: "A row of photos visitors can swipe.", fields: [{ k: "title", t: "text", label: "Gallery title (optional)" }, { k: "images", t: "images" }] },
    grid: { label: "Image grid (2 or 3 columns)", icon: "grid_view", group: "Media", desc: "Photos side by side in a grid.", fields: [{ k: "columns", t: "select", label: "Columns", options: [["2", "2 columns"], ["3", "3 columns"]] }, { k: "images", t: "images" }] },
    image_text: { label: "Image + text split", icon: "vertical_split", group: "Media", desc: "A photo beside a paragraph.", fields: [F.url, { k: "side", t: "select", label: "Photo on the", options: [["left", "Left"], ["right", "Right"]] }, { k: "title", t: "text", label: "Title (optional)" }, { k: "text", t: "textarea", label: "Text", rows: 5, help: TEXT_HELP }, F.caption] },
    video: { label: "Video story", icon: "smart_display", group: "Media", desc: "A YouTube or Vimeo video.", fields: [{ k: "url", t: "text", label: "YouTube or Vimeo link", ph: "https://www.youtube.com/watch?v=…" }, F.caption] },
    embed: { label: "Interactive embed", icon: "code", group: "Media", desc: "A map, Instagram post, playlist or weather map.", fields: [{ k: "url", t: "text", label: "Embed link", ph: "https://www.google.com/maps/embed?…", help: "Google Maps (Share → Embed a map → copy the src link), YouTube, Vimeo, Instagram, Spotify, Windy or Google Docs." }, { k: "height", t: "number", label: "Height in pixels", ph: "450" }, F.caption] },
    cta: { label: "Editorial call to action", icon: "campaign", group: "Promote", desc: "A banner with a button.", fields: [F.title, { k: "text", t: "textarea", label: "Text", rows: 2 }, { k: "button_label", t: "text", label: "Button text", ph: "Find a guest house" }, { k: "button_url", t: "text", label: "Button link", ph: "/stays/" }, { k: "style", t: "select", label: "Style", options: [["dark", "Lagoon (dark)"], ["light", "Shallows (light)"], ["gold", "Gold"]] }] },
    stay: { label: "Hotel / property spotlight", icon: "hotel", group: "Promote", desc: "Feature guest houses and hotels from the site.", fields: [{ k: "title", t: "text", label: "Title (optional)", ph: "Where to stay" }, { k: "items", t: "pick", source: "listings", group: "stay", label: "Places to stay" }, F.note] },
    experience: { label: "Experience reference", icon: "sailing", group: "Promote", desc: "Feature excursion and dive operators.", fields: [{ k: "title", t: "text", label: "Title (optional)", ph: "Book a trip" }, { k: "items", t: "pick", source: "listings", group: "experience", label: "Experiences" }, F.note] },
    island: { label: "Destination / island spotlight", icon: "landscape", group: "Promote", desc: "An island card with key facts and links.", fields: [{ k: "island", t: "island", label: "Island" }, { k: "note", t: "textarea", label: "Why go (optional, otherwise the island's tagline)", rows: 2 }] },
    related: { label: "Related articles section", icon: "auto_stories", group: "Promote", desc: "Links to other guides.", fields: [{ k: "title", t: "text", label: "Title", ph: "Read next" }, { k: "items", t: "pick", source: "guides", label: "Guides", help: "Leave empty to show guides from the same topic." }] },
  };
  var ORDER = ["rich_text", "heading", "image", "hero_image", "gallery", "grid", "image_text", "quote", "video", "embed", "cta", "stay", "experience", "island", "related", "facts"];

  // Small drawings for the block library.
  var C = { ink: "#0A3D4C", sea: "#0B6E8A", sh: "#4CC3C7", line: "#CFDDE1", soft: "#E8F4F5", gold: "#EBA62A" };
  function bar(x, y, w, h, c) { return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + (h || 5) + '" rx="2.5" fill="' + (c || C.line) + '"/>'; }
  function pic(x, y, w, h) { return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="6" fill="' + C.sh + '" opacity=".55"/><path d="M' + x + ' ' + (y + h) + ' l' + w * .35 + ' -' + h * .45 + ' l' + w * .2 + ' ' + h * .25 + ' l' + w * .2 + ' -' + h * .3 + ' l' + w * .25 + ' ' + h * .5 + 'z" fill="' + C.sea + '" opacity=".7"/><circle cx="' + (x + w * .78) + '" cy="' + (y + h * .3) + '" r="' + h * .1 + '" fill="#fff" opacity=".9"/>'; }
  var TH = {
    rich_text: bar(20, 22, 120) + bar(20, 34, 110) + bar(20, 46, 118) + bar(20, 58, 90) + bar(20, 74, 115) + bar(20, 86, 70),
    heading: bar(20, 26, 90, 10, C.ink) + bar(20, 46, 120) + bar(20, 58, 100) + bar(20, 76, 115) + bar(20, 88, 80),
    image: pic(20, 14, 120, 62) + bar(40, 84, 80),
    hero_image: pic(0, 10, 160, 72) + bar(20, 88, 60),
    gallery: pic(6, 22, 60, 50) + pic(72, 22, 60, 50) + '<rect x="138" y="22" width="30" height="50" rx="6" fill="' + C.sh + '" opacity=".35"/>' + '<circle cx="74" cy="86" r="3" fill="' + C.sea + '"/><circle cx="84" cy="86" r="3" fill="' + C.line + '"/><circle cx="94" cy="86" r="3" fill="' + C.line + '"/>',
    grid: pic(14, 16, 42, 34) + pic(60, 16, 42, 34) + pic(106, 16, 42, 34) + pic(14, 54, 42, 34) + pic(60, 54, 42, 34) + pic(106, 54, 42, 34),
    image_text: pic(14, 20, 66, 60) + bar(90, 26, 50, 8, C.ink) + bar(90, 42, 56) + bar(90, 54, 50) + bar(90, 66, 54),
    quote: '<text x="18" y="56" font-size="54" font-family="Georgia" fill="' + C.sh + '">“</text>' + bar(50, 34, 92, 8, C.ink) + bar(50, 50, 80, 8, C.ink) + bar(50, 70, 50, 5, C.sea),
    video: '<rect x="20" y="14" width="120" height="70" rx="8" fill="' + C.ink + '"/><circle cx="80" cy="49" r="15" fill="#fff"/><path d="M75 41 l13 8 l-13 8z" fill="' + C.ink + '"/>' + bar(40, 90, 80),
    embed: '<rect x="20" y="14" width="120" height="72" rx="8" fill="' + C.soft + '" stroke="' + C.line + '"/><path d="M30 70 Q60 30 80 55 T130 34" stroke="' + C.sea + '" stroke-width="4" fill="none"/><circle cx="80" cy="55" r="6" fill="' + C.gold + '"/>',
    cta: '<rect x="12" y="24" width="136" height="52" rx="10" fill="' + C.ink + '"/>' + bar(24, 38, 60, 7, "#fff") + bar(24, 52, 46, 5, C.sh) + '<rect x="98" y="40" width="40" height="18" rx="9" fill="' + C.gold + '"/>',
    stay: '<rect x="14" y="14" width="62" height="74" rx="8" fill="#fff" stroke="' + C.line + '"/>' + pic(14, 14, 62, 38) + bar(20, 60, 44, 6, C.ink) + bar(20, 72, 32) + '<rect x="84" y="14" width="62" height="74" rx="8" fill="#fff" stroke="' + C.line + '"/>' + pic(84, 14, 62, 38) + bar(90, 60, 44, 6, C.ink) + bar(90, 72, 32),
    experience: '<rect x="14" y="14" width="62" height="74" rx="8" fill="#fff" stroke="' + C.line + '"/>' + pic(14, 14, 62, 38) + bar(20, 60, 44, 6, C.ink) + '<circle cx="62" cy="44" r="8" fill="#fff"/><rect x="84" y="14" width="62" height="74" rx="8" fill="#fff" stroke="' + C.line + '"/>' + pic(84, 14, 62, 38) + bar(90, 60, 44, 6, C.ink) + '<circle cx="132" cy="44" r="8" fill="#fff"/>',
    island: '<rect x="10" y="16" width="140" height="68" rx="10" fill="#fff" stroke="' + C.line + '"/>' + pic(10, 16, 58, 68) + bar(76, 28, 50, 8, C.ink) + bar(76, 44, 64) + '<rect x="76" y="58" width="28" height="12" rx="6" fill="' + C.sea + '"/><rect x="108" y="58" width="28" height="12" rx="6" fill="' + C.soft + '"/>',
    related: [24, 46, 68].map(function (y) { return '<rect x="14" y="' + (y - 6) + '" width="132" height="18" rx="5" fill="#fff" stroke="' + C.line + '"/><rect x="18" y="' + (y - 3) + '" width="18" height="12" rx="3" fill="' + C.sh + '" opacity=".6"/>' + bar(42, y, 70, 5, C.ink); }).join("") + bar(14, 88, 40, 5, C.sea),
    facts: '<rect x="14" y="12" width="132" height="78" rx="10" fill="' + C.soft + '" stroke="' + C.sh + '"/><circle cx="28" cy="26" r="6" fill="' + C.sea + '"/>' + bar(40, 23, 50, 7, C.ink) + [42, 56, 70].map(function (y) { return bar(26, y, 34, 5, C.sea) + bar(70, y, 62); }).join(""),
  };
  function thumb(t) { return '<svg viewBox="0 0 160 100" aria-hidden="true"><rect width="160" height="100" rx="10" fill="#F6FAFB"/>' + (TH[t] || "") + "</svg>"; }

  // ------------------------------------------------------------------ helpers
  function $(n) { return document.querySelector('form [name="' + n + '"]'); }
  function val(n) { var f = $(n); return f ? f.value : ""; }
  function set(n, v) { var f = $(n); if (!f) return; f.value = v; f.dispatchEvent(new Event("input", { bubbles: true })); f.dispatchEvent(new Event("change", { bubbles: true })); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function el(html) { var d = document.createElement("div"); d.innerHTML = html.trim(); return d.firstChild; }
  var uid = 0;
  function newBlock(type) {
    var b = { type: type, _id: ++uid };
    if (type === "grid") b.columns = "2";
    if (type === "image_text") b.side = "left";
    if (type === "cta") b.style = "dark";
    if (type === "embed") b.height = 450;
    if (type === "facts") b.items = [{ label: "", value: "" }, { label: "", value: "" }];
    if (type === "gallery" || type === "grid") b.images = [];
    if (type === "stay" || type === "experience" || type === "related") b.items = [];
    return b;
  }
  function textToBlocks(text) {
    var out = [], cur = [];
    function flush() { var t = cur.join("\n").trim(); if (t) out.push({ type: "rich_text", text: t, _id: ++uid }); cur = []; }
    (text || "").split("\n").forEach(function (line) {
      if (line.indexOf("## ") === 0) { flush(); out.push({ type: "heading", title: line.slice(3).trim(), intro: "", _id: ++uid }); }
      else cur.push(line);
    });
    flush();
    return out;
  }
  function blocksToText(blocks) {
    return blocks.map(function (b) {
      switch (b.type) {
        case "heading": return b.title ? "## " + b.title + (b.intro ? "\n\n" + b.intro : "") : "";
        case "rich_text": return b.text || "";
        case "image_text": return [b.title, b.text].filter(Boolean).join("\n\n");
        case "quote": return b.quote || "";
        case "cta": return [b.title, b.text].filter(Boolean).join(" ") + (b.button_url ? " [" + (b.button_label || "More") + "](" + b.button_url + ")" : "");
        case "facts": return [b.title].concat((b.items || []).map(function (r) { return "- **" + (r.label || "") + ":** " + (r.value || ""); })).concat([b.note]).filter(Boolean).join("\n");
        default: return [b.title, b.note, b.caption].filter(Boolean).join(" ");
      }
    }).filter(function (x) { return x && x.trim(); }).join("\n\n");
  }

  // ------------------------------------------------------------------ state
  var blocksField = $("blocks"), bodyField = $("body");
  var blocks = [];
  try { blocks = JSON.parse(blocksField.value || "[]"); } catch (e) { blocks = []; }
  if (!blocks.length && bodyField && bodyField.value.trim()) blocks = textToBlocks(bodyField.value);
  blocks.forEach(function (b) { b._id = ++uid; });
  var open = {};
  function save() {
    blocksField.value = JSON.stringify(blocks.map(function (b) { var c = Object.assign({}, b); delete c._id; return c; }));
    if (bodyField) bodyField.value = blocksToText(blocks);
    refresh();
  }

  // ------------------------------------------------------------------ editor UI
  var host = document.getElementById("ge-blocks");
  var bodyRow = bodyField && (bodyField.closest(".field-body") || bodyField.closest(".form-row") || bodyField.parentNode);
  if (bodyRow) { bodyRow.parentNode.insertBefore(host, bodyRow); bodyRow.style.display = "none"; }
  var blocksRow = blocksField.closest(".field-blocks") || blocksField.closest(".form-row");
  if (blocksRow && blocksRow !== bodyRow) blocksRow.style.display = "none";
  host.hidden = false;
  var list = host.querySelector(".gb-list");

  function fieldHtml(b, f, i) {
    var v = b[f.k] == null ? "" : b[f.k], id = "gb" + b._id + "-" + f.k;
    var lab = f.label ? '<label for="' + id + '">' + esc(f.label) + "</label>" : "";
    var help = f.help ? '<small class="gb-help">' + esc(f.help) + "</small>" : "";
    switch (f.t) {
      case "text": return '<div class="gb-f">' + lab + '<input id="' + id + '" type="text" data-k="' + f.k + '" value="' + esc(v) + '" placeholder="' + esc(f.ph || "") + '">' + help + "</div>";
      case "number": return '<div class="gb-f gb-f-s">' + lab + '<input id="' + id + '" type="number" data-k="' + f.k + '" value="' + esc(v) + '" placeholder="' + esc(f.ph || "") + '">' + help + "</div>";
      case "textarea": return '<div class="gb-f">' + lab + '<textarea id="' + id + '" rows="' + (f.rows || 4) + '" data-k="' + f.k + '" placeholder="' + esc(f.ph || "") + '">' + esc(v) + "</textarea>" + help + "</div>";
      case "select": return '<div class="gb-f gb-f-s">' + lab + '<select id="' + id + '" data-k="' + f.k + '">' + f.options.map(function (o) { return '<option value="' + o[0] + '"' + (String(v) === o[0] ? " selected" : "") + ">" + esc(o[1]) + "</option>"; }).join("") + "</select></div>";
      case "image": return '<div class="gb-f gb-img">' + (v ? '<img src="' + esc(v) + '" alt="">' : '<span class="gb-img-empty material-symbols-outlined">add_photo_alternate</span>') +
        '<div><label for="' + id + '">' + esc(f.label || "Photo") + '</label><input id="' + id + '" type="text" data-k="' + f.k + '" value="' + esc(v) + '" placeholder="Paste a photo link, or upload">' +
        '<label class="gb-upload"><span class="material-symbols-outlined">upload</span>Upload photo<input type="file" accept="image/*" data-upload="' + f.k + '" hidden></label></div></div>';
      case "island": return '<div class="gb-f">' + lab + '<select id="' + id + '" data-k="' + f.k + '" data-int="1"><option value="">Choose an island…</option>' + ISLANDS.map(function (s) { return '<option value="' + s.id + '"' + (String(v) === String(s.id) ? " selected" : "") + ">" + esc(s.name + " · " + s.atoll) + "</option>"; }).join("") + "</select></div>";
      case "images":
        return '<div class="gb-f"><label>Photos</label><div class="gb-imgs">' + (b.images || []).map(function (im, n) {
          return '<div class="gb-imgrow" data-n="' + n + '">' + (im.url ? '<img src="' + esc(im.url) + '" alt="">' : '<span class="gb-img-empty material-symbols-outlined">image</span>') +
            '<input type="text" data-img="url" value="' + esc(im.url) + '" placeholder="Photo link"><input type="text" data-img="caption" value="' + esc(im.caption) + '" placeholder="Caption">' +
            '<button type="button" class="gb-icon" data-img-del title="Remove"><span class="material-symbols-outlined">close</span></button></div>';
        }).join("") + '</div><div class="gb-row"><button type="button" class="gb-mini" data-img-add><span class="material-symbols-outlined">add</span>Add photo link</button>' +
          '<label class="gb-mini"><span class="material-symbols-outlined">upload</span>Upload photos<input type="file" accept="image/*" multiple data-upload-many hidden></label></div></div>';
      case "facts":
        return '<div class="gb-f"><label>Facts</label><div class="gb-facts-rows">' + (b.items || []).map(function (r, n) {
          return '<div class="gb-factrow" data-n="' + n + '"><input type="text" data-fact="label" value="' + esc(r.label) + '" placeholder="e.g. Best time"><input type="text" data-fact="value" value="' + esc(r.value) + '" placeholder="e.g. November to April">' +
            '<button type="button" class="gb-icon" data-fact-del title="Remove"><span class="material-symbols-outlined">close</span></button></div>';
        }).join("") + '</div><button type="button" class="gb-mini" data-fact-add><span class="material-symbols-outlined">add</span>Add a fact</button></div>';
      case "pick":
        var src = PICK[f.source].filter(function (x) { return !f.group || x.group === f.group; });
        var chosen = (b[f.k] || []).map(function (id) { return src.find(function (x) { return x.id === id; }); }).filter(Boolean);
        return '<div class="gb-f gb-pick" data-src="' + f.source + '" data-group="' + (f.group || "") + '">' + lab + '<div class="gb-chips">' + chosen.map(function (c) {
          return '<span class="gb-chip">' + esc(c.name) + '<button type="button" data-unpick="' + c.id + '" aria-label="Remove">×</button></span>';
        }).join("") + '</div><div class="gb-pick-box"><input type="text" data-pick-q placeholder="Type to search ' + src.length + ' ' + esc((f.label || "items").toLowerCase()) + '…"><div class="gb-pick-list" hidden></div></div>' + help + "</div>";
    }
    return "";
  }
  function summary(b) {
    var s = b.title || b.text || b.quote || b.caption || b.url || "";
    if (b.type === "island") { var i = ISLANDS.find(function (x) { return String(x.id) === String(b.island); }); s = i ? i.name : ""; }
    if ((b.type === "gallery" || b.type === "grid") && b.images) s = b.images.length + " photo" + (b.images.length === 1 ? "" : "s");
    if (b.items && (b.type === "stay" || b.type === "experience" || b.type === "related")) s = (b.title ? b.title + " · " : "") + b.items.length + " chosen";
    return String(s).replace(/\s+/g, " ").slice(0, 80);
  }
  function render() {
    list.innerHTML = "";
    if (!blocks.length) {
      list.appendChild(el('<div class="gb-empty"><span class="material-symbols-outlined">dashboard_customize</span><b>No content yet</b><p>Start from a template above, or add your first block.</p></div>'));
    }
    blocks.forEach(function (b, idx) {
      var T = BLOCKS[b.type]; if (!T) return;
      var isOpen = open[b._id] !== false;
      var card = el('<div class="gb-card' + (isOpen ? " open" : "") + '" data-id="' + b._id + '">' +
        '<div class="gb-card-head" draggable="true"><span class="gb-drag material-symbols-outlined" title="Drag to move">drag_indicator</span>' +
        '<span class="gb-type material-symbols-outlined">' + T.icon + '</span><b>' + esc(T.label) + '</b><span class="gb-sum">' + esc(isOpen ? "" : summary(b)) + "</span>" +
        '<span class="gb-actions"><button type="button" class="gb-icon" data-act="up" title="Move up"' + (idx === 0 ? " disabled" : "") + '><span class="material-symbols-outlined">arrow_upward</span></button>' +
        '<button type="button" class="gb-icon" data-act="down" title="Move down"' + (idx === blocks.length - 1 ? " disabled" : "") + '><span class="material-symbols-outlined">arrow_downward</span></button>' +
        '<button type="button" class="gb-icon" data-act="dup" title="Duplicate"><span class="material-symbols-outlined">content_copy</span></button>' +
        '<button type="button" class="gb-icon" data-act="del" title="Delete"><span class="material-symbols-outlined">delete</span></button>' +
        '<button type="button" class="gb-icon" data-act="toggle" title="' + (isOpen ? "Collapse" : "Expand") + '"><span class="material-symbols-outlined">' + (isOpen ? "expand_less" : "expand_more") + "</span></button></span></div>" +
        '<div class="gb-card-body">' + T.fields.map(function (f) { return fieldHtml(b, f); }).join("") + "</div></div>");
      list.appendChild(el('<button type="button" class="gb-insert" data-at="' + idx + '" title="Add a block here"><span class="material-symbols-outlined">add</span></button>'));
      list.appendChild(card);
    });
    save();
  }
  function blockOf(node) { var c = node.closest(".gb-card"); return c ? blocks.find(function (b) { return String(b._id) === c.dataset.id; }) : null; }

  list.addEventListener("input", function (e) {
    var b = blockOf(e.target); if (!b) return;
    var t = e.target;
    if (t.dataset.k) { b[t.dataset.k] = t.dataset.int ? (parseInt(t.value, 10) || null) : (t.type === "number" ? (parseInt(t.value, 10) || "") : t.value); }
    if (t.dataset.img) { var n = +t.closest(".gb-imgrow").dataset.n; b.images[n][t.dataset.img] = t.value; }
    if (t.dataset.fact) { var m = +t.closest(".gb-factrow").dataset.n; b.items[m][t.dataset.fact] = t.value; }
    if (t.dataset.pickQ !== undefined) { pickSearch(t, b); return; }
    save();
  });
  list.addEventListener("change", function (e) {
    var t = e.target, b = blockOf(t); if (!b) return;
    if (t.tagName === "SELECT" && t.dataset.k) { b[t.dataset.k] = t.dataset.int ? (parseInt(t.value, 10) || null) : t.value; save(); }
    if (t.dataset.k === "url" && t.closest(".gb-img")) render();
    if (t.dataset.img === "url") render();
    if (t.dataset.upload) { upload(t.files[0]).then(function (u) { b[t.dataset.upload] = u; render(); }); }
    if (t.dataset.uploadMany !== undefined) {
      var files = Array.prototype.slice.call(t.files);
      files.reduce(function (p, f) { return p.then(function () { return upload(f).then(function (u) { b.images.push({ url: u, caption: "" }); }); }); }, Promise.resolve())
        .then(render, render);
    }
  });
  list.addEventListener("click", function (e) {
    var a = e.target.closest("[data-act],[data-at],[data-img-add],[data-img-del],[data-fact-add],[data-fact-del],[data-unpick],[data-pick]");
    if (!a) {
      var head = e.target.closest(".gb-card-head");
      if (head && !e.target.closest("button")) { var hb = blockOf(head); open[hb._id] = open[hb._id] === false; render(); }
      return;
    }
    if (a.dataset.at !== undefined) { openLibrary(+a.dataset.at); return; }
    var b = blockOf(a), i = blocks.indexOf(b);
    if (a.dataset.act === "up" && i > 0) { blocks.splice(i - 1, 0, blocks.splice(i, 1)[0]); }
    else if (a.dataset.act === "down" && i < blocks.length - 1) { blocks.splice(i + 1, 0, blocks.splice(i, 1)[0]); }
    else if (a.dataset.act === "dup") { var c = JSON.parse(JSON.stringify(b)); c._id = ++uid; blocks.splice(i + 1, 0, c); }
    else if (a.dataset.act === "del") { if (!confirm("Delete this " + BLOCKS[b.type].label.toLowerCase() + " block?")) return; blocks.splice(i, 1); }
    else if (a.dataset.act === "toggle") { open[b._id] = open[b._id] === false; }
    else if (a.dataset.imgAdd !== undefined) { b.images.push({ url: "", caption: "" }); }
    else if (a.dataset.imgDel !== undefined) { b.images.splice(+a.closest(".gb-imgrow").dataset.n, 1); }
    else if (a.dataset.factAdd !== undefined) { b.items.push({ label: "", value: "" }); }
    else if (a.dataset.factDel !== undefined) { b.items.splice(+a.closest(".gb-factrow").dataset.n, 1); }
    else if (a.dataset.unpick) { b.items = b.items.filter(function (x) { return String(x) !== a.dataset.unpick; }); }
    else if (a.dataset.pick) { if (b.items.indexOf(+a.dataset.pick) < 0) b.items.push(+a.dataset.pick); }
    render();
  });
  function pickSearch(input, b) {
    var wrap = input.closest(".gb-pick"), box = wrap.querySelector(".gb-pick-list"), q = input.value.trim().toLowerCase();
    var src = PICK[wrap.dataset.src].filter(function (x) { return (!wrap.dataset.group || x.group === wrap.dataset.group) && b.items.indexOf(x.id) < 0; });
    var hits = src.filter(function (x) { return !q || (x.name + " " + x.sub).toLowerCase().indexOf(q) > -1; }).slice(0, 8);
    box.innerHTML = hits.length ? hits.map(function (x) { return '<button type="button" data-pick="' + x.id + '"><b>' + esc(x.name) + "</b><small>" + esc(x.sub) + "</small></button>"; }).join("") : '<p class="gb-help">Nothing found.</p>';
    box.hidden = false;
  }
  list.addEventListener("focusin", function (e) { if (e.target.dataset && e.target.dataset.pickQ !== undefined) pickSearch(e.target, blockOf(e.target)); });

  // drag to reorder
  var dragId = null;
  list.addEventListener("dragstart", function (e) { var c = e.target.closest(".gb-card"); if (!c) return; dragId = c.dataset.id; c.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; });
  list.addEventListener("dragend", function () { dragId = null; list.querySelectorAll(".dragging,.drop-before").forEach(function (n) { n.classList.remove("dragging", "drop-before"); }); });
  list.addEventListener("dragover", function (e) {
    if (!dragId) return; e.preventDefault();
    var c = e.target.closest(".gb-card"); list.querySelectorAll(".drop-before").forEach(function (n) { n.classList.remove("drop-before"); });
    if (c && c.dataset.id !== dragId) c.classList.add("drop-before");
  });
  list.addEventListener("drop", function (e) {
    if (!dragId) return; e.preventDefault();
    var c = e.target.closest(".gb-card"); if (!c || c.dataset.id === dragId) return;
    var from = blocks.findIndex(function (b) { return String(b._id) === dragId; }), moved = blocks.splice(from, 1)[0];
    var to = blocks.findIndex(function (b) { return String(b._id) === c.dataset.id; });
    blocks.splice(to, 0, moved); render();
  });

  function upload(file) {
    if (!file) return Promise.reject();
    var status = document.getElementById("ge-pv-status"), fd = new FormData(); fd.append("file", file);
    host.classList.add("uploading");
    return fetch(DATA.upload, { method: "POST", body: fd, headers: { "X-CSRFToken": csrf }, credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) { host.classList.remove("uploading"); if (d.error) { alert(d.error); throw new Error(d.error); } return d.url; })
      .catch(function (e) { host.classList.remove("uploading"); throw e; });
  }

  // ------------------------------------------------------------------ block library
  var lib = document.getElementById("gb-lib"), libGrid = lib.querySelector(".gb-lib-grid"), libQ = lib.querySelector("input"), insertAt = null;
  libGrid.innerHTML = ORDER.map(function (t) {
    var T = BLOCKS[t];
    return '<button type="button" class="gb-lib-item" data-type="' + t + '" data-q="' + esc((T.label + " " + T.desc + " " + T.group).toLowerCase()) + '">' + thumb(t) +
      '<span><b>' + esc(T.label) + "</b><small>" + esc(T.desc) + "</small></span></button>";
  }).join("");
  function openLibrary(at) { insertAt = at; lib.hidden = false; libQ.value = ""; filterLib(); setTimeout(function () { libQ.focus(); }, 30); }
  function closeLibrary() { lib.hidden = true; }
  function filterLib() { var q = libQ.value.trim().toLowerCase(); libGrid.querySelectorAll(".gb-lib-item").forEach(function (b) { b.hidden = q && b.dataset.q.indexOf(q) < 0; }); }
  libQ.addEventListener("input", filterLib);
  libQ.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); var f = libGrid.querySelector(".gb-lib-item:not([hidden])"); if (f) f.click(); } if (e.key === "Escape") closeLibrary(); });
  lib.addEventListener("click", function (e) {
    if (e.target === lib || e.target.closest("[data-close]")) { closeLibrary(); return; }
    var it = e.target.closest(".gb-lib-item"); if (!it) return;
    var b = newBlock(it.dataset.type), at = insertAt == null ? blocks.length : insertAt;
    blocks.splice(at, 0, b); closeLibrary(); render();
    setTimeout(function () { var c = list.querySelector('[data-id="' + b._id + '"]'); if (c) { c.scrollIntoView({ behavior: "smooth", block: "center" }); var f = c.querySelector("input,textarea,select"); if (f) f.focus(); } }, 50);
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !lib.hidden) closeLibrary(); });
  host.querySelectorAll("[data-add-block]").forEach(function (b) { b.addEventListener("click", function () { openLibrary(null); }); });
  host.querySelector("[data-collapse-all]").addEventListener("click", function () {
    var anyOpen = blocks.some(function (b) { return open[b._id] !== false; });
    blocks.forEach(function (b) { open[b._id] = !anyOpen; }); render();
  });

  // ------------------------------------------------------------------ templates and island fill
  root.querySelectorAll("[data-tpl]").forEach(function (b) {
    b.addEventListener("click", function () {
      var t = TPLS.find(function (x) { return String(x.id) === b.dataset.tpl; });
      if (!t) return;
      if (blocks.length && !confirm("Replace the title, summary, content and questions with the “" + t.name + "” template?")) return;
      set("title", t.title); set("summary", t.summary); set("faqs", t.faqs); set("category", t.category);
      blocks = textToBlocks(t.body); open = {};
      root.querySelectorAll(".ge-tpl").forEach(function (x) { x.classList.toggle("on", x === b); });
      render(); document.getElementById("ge-island").focus();
    });
  });
  var isl = document.getElementById("ge-island");
  ISLANDS.forEach(function (i) { var o = document.createElement("option"); o.value = i.id; o.textContent = i.name + " · " + i.atoll; isl.appendChild(o); });
  function replaceAll(v, map) {
    if (typeof v === "string") { Object.keys(map).forEach(function (k) { v = v.split(k).join(map[k]); }); return v; }
    if (Array.isArray(v)) return v.map(function (x) { return replaceAll(x, map); });
    if (v && typeof v === "object") { var o = {}; Object.keys(v).forEach(function (k) { o[k] = k === "_id" ? v[k] : replaceAll(v[k], map); }); return o; }
    return v;
  }
  document.getElementById("ge-fill-island").addEventListener("click", function () {
    var i = ISLANDS.find(function (x) { return String(x.id) === isl.value; });
    if (!i) { isl.focus(); return; }
    var map = { "[Island]": i.name, "[Island A]": i.name, "[Atoll]": i.atoll, "[time]": i.time || "[time]", "[distance]": String(i.km || "[distance]"), "[island-slug]": i.slug, "[island-a-slug]": i.slug, "[slug]": i.slug };
    ["title", "summary", "faqs"].forEach(function (n) { set(n, replaceAll(val(n), map)); });
    blocks = replaceAll(blocks, map);
    var from = document.getElementById("id_islands_from"), to = document.getElementById("id_islands_to");
    if (from && to && !Array.prototype.some.call(to.options, function (o) { return o.value === String(i.id); })) {
      var opt = Array.prototype.find.call(from.options, function (o) { return o.value === String(i.id); }); if (opt) to.appendChild(opt);
    } else if (!to) { var s = $("islands"); if (s) Array.prototype.forEach.call(s.options, function (o) { if (o.value === String(i.id)) o.selected = true; }); }
    render();
  });

  // ------------------------------------------------------------------ checklist
  function islandIds() {
    var to = document.getElementById("id_islands_to");
    if (to) return Array.prototype.map.call(to.options, function (o) { return o.value; });
    var s = $("islands"); return s ? Array.prototype.filter.call(s.options, function (o) { return o.selected; }).map(function (o) { return o.value; }) : [];
  }
  function check() {
    var title = val("title"), summary = val("summary"), body = blocksToText(blocks), faqs = val("faqs");
    var all = [title, summary, body, faqs].join("\n");
    var todo = (all.match(/\[[^\]\n]{1,80}\](?!\()/g) || []).length;
    var words = (body + " " + faqs).trim().split(/\s+/).filter(Boolean).length;
    var heads = blocks.filter(function (b) { return b.type === "heading" && b.title; }).length + ((body.match(/^## /gm) || []).length - blocks.filter(function (b) { return b.type === "heading" && b.title; }).length);
    var qs = (faqs.match(/^Q:/gim) || []).length;
    var links = (body.match(/\]\(\//g) || []).length + blocks.filter(function (b) { return ["stay", "experience", "island", "related"].indexOf(b.type) > -1; }).length;
    var photos = blocks.filter(function (b) { return (b.url && /image/.test(b.type)) || (b.images && b.images.length); }).length;
    var cover = val("cover_image_url") || root.dataset.photo || ($("cover_image") || {}).value || photos || islandIds().length;
    var items = [
      [todo === 0, todo ? todo + " [prompt" + (todo > 1 ? "s" : "") + "] still to replace" : "All [prompts] replaced"],
      [title.length >= 20 && title.length <= 70, "Title " + title.length + " characters (best 20–70)"],
      [summary.length >= 70 && summary.length <= 160, "Summary " + summary.length + " characters (best 70–160, shown in Google)"],
      [words >= 600, words + " words (aim for 600+ to rank well)"],
      [heads >= 3, heads + " heading" + (heads === 1 ? "" : "s") + " (aim for 3+)"],
      [photos >= 2, photos + " photo block" + (photos === 1 ? "" : "s") + " (aim for 2+)"],
      [qs >= 2, qs + " question" + (qs === 1 ? "" : "s") + " and answers (aim for 2+)"],
      [links >= 2, links + " link" + (links === 1 ? "" : "s") + " or spotlights to other pages (aim for 2+)"],
      [islandIds().length > 0, islandIds().length ? islandIds().length + " island" + (islandIds().length > 1 ? "s" : "") + " linked" : "No islands linked yet"],
      [!!cover, cover ? "Has a cover photo" : "No cover photo yet"],
    ];
    var done = items.filter(function (i) { return i[0]; }).length;
    document.getElementById("ge-check").innerHTML = items.map(function (i) {
      return '<li class="' + (i[0] ? "ok" : "todo") + '"><span class="material-symbols-outlined">' + (i[0] ? "check_circle" : "radio_button_unchecked") + "</span>" + esc(i[1]).replace(/\[/g, "&#91;") + "</li>";
    }).join("");
    document.getElementById("ge-stats").textContent = done + " of " + items.length + " done · " + Math.max(1, Math.round(words / 220)) + " min read";
    document.getElementById("ge-score").style.setProperty("--p", Math.round(done / items.length * 100));
  }

  // ------------------------------------------------------------------ live preview
  var drawer = document.getElementById("ge-drawer"), frame = document.getElementById("ge-frame"), timer, busy = false, again = false;
  function renderPreview() {
    if (drawer.hidden) return;
    if (busy) { again = true; return; }
    busy = true; document.getElementById("ge-pv-status").textContent = "Updating…";
    var fd = new FormData();
    ["title", "summary", "faqs", "category", "cover_image_url", "cover_credit", "author"].forEach(function (n) { fd.append(n, val(n)); });
    fd.append("blocks", blocksField.value); fd.append("body", "");
    islandIds().forEach(function (id) { fd.append("islands", id); });
    fd.append("current_photo", root.dataset.photo || "");
    var y = 0; try { y = frame.contentWindow.scrollY; } catch (e) {}
    fetch(DATA.preview, { method: "POST", body: fd, headers: { "X-CSRFToken": csrf }, credentials: "same-origin" })
      .then(function (r) { return r.text(); })
      .then(function (html) { frame.onload = function () { try { frame.contentWindow.scrollTo(0, y); } catch (e) {} }; frame.srcdoc = html; document.getElementById("ge-pv-status").textContent = "Up to date"; })
      .catch(function () { document.getElementById("ge-pv-status").textContent = "Preview failed. Try again."; })
      .finally(function () { busy = false; if (again) { again = false; renderPreview(); } });
  }
  function refresh(now) { check(); clearTimeout(timer); timer = setTimeout(renderPreview, now ? 0 : 700); }
  function openPreview() { drawer.hidden = false; document.body.classList.add("ge-open"); try { localStorage.setItem("ge_preview", "1"); } catch (e) {} renderPreview(); }
  function closePreview() { drawer.hidden = true; document.body.classList.remove("ge-open"); try { localStorage.setItem("ge_preview", "0"); } catch (e) {} }
  document.getElementById("ge-open-preview").addEventListener("click", function () { drawer.hidden ? openPreview() : closePreview(); });
  document.getElementById("ge-close").addEventListener("click", closePreview);
  drawer.querySelectorAll("[data-w]").forEach(function (b) {
    b.addEventListener("click", function () { drawer.querySelectorAll("[data-w]").forEach(function (x) { x.classList.toggle("on", x === b); }); frame.style.width = b.dataset.w; });
  });
  document.addEventListener("input", function (e) { if (e.target.closest && e.target.closest("form") && !e.target.closest(".gb-list")) refresh(); });
  document.addEventListener("change", function (e) { if (e.target.closest && e.target.closest("form") && !e.target.closest(".gb-list")) refresh(); });
  document.addEventListener("click", function (e) { if (e.target.closest && e.target.closest(".selector-chooser, .selector")) setTimeout(refresh, 50); });

  render();
  var pref = null; try { pref = localStorage.getItem("ge_preview"); } catch (e) {}
  if (window.innerWidth >= 1280 && pref !== "0") openPreview();
})();
