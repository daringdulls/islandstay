/* Turn any social design into a short Reel video: the photo slowly zooms ("Ken Burns") under the
 * text and logo, which stay still. Encoded frame by frame with the browser's H.264 encoder (WebCodecs)
 * and packed into an MP4 with mp4-muxer. Needs html-to-image (htmlToImage) and Mp4Muxer on the page. */
(function () {
  function ease(t) { return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }

  async function bitmap(img) {
    try { await img.decode(); } catch (e) { /* already loaded */ }
    try { return await createImageBitmap(img); } catch (e) {
      var r = await fetch(img.currentSrc || img.src, { credentials: 'same-origin' });
      return await createImageBitmap(await r.blob());
    }
  }

  // Draw `bmp` like object-fit: cover into the box, scaled by `s` around the focus point.
  function cover(ctx, bmp, box, s, fx, fy) {
    var k = Math.max(box.w / bmp.width, box.h / bmp.height) * s;
    var dw = bmp.width * k, dh = bmp.height * k;
    var dx = box.x + (box.w - dw) * fx, dy = box.y + (box.h - dh) * fy;
    ctx.drawImage(bmp, dx, dy, dw, dh);
  }

  window.IslandReel = {
    supported: function () { return !!(window.VideoEncoder && window.VideoFrame && window.Mp4Muxer); },

    record: async function (sp, seconds, onProgress) {
      if (!this.supported()) throw new Error('This browser cannot make MP4 video. Use Chrome or Edge (version 94 or newer).');
      var w = +sp.dataset.w, h = +sp.dataset.h;
      var rect = sp.getBoundingClientRect(), k = w / rect.width;
      var imgs = Array.prototype.slice.call(sp.querySelectorAll('.sp-photo > img')).filter(function (i) { return i.offsetWidth > 0; });
      await document.fonts.ready;
      var opts = { width: w, height: h, pixelRatio: 1, style: { transform: 'none' } };

      // 1. layers: the photos on their own, and the rest of the design with see-through holes where the photos were
      var photos = [];
      try {
        for (var i = 0; i < imgs.length; i++) {
          var b = imgs[i].parentNode.getBoundingClientRect();
          photos.push({ bmp: await bitmap(imgs[i]), box: { x: (b.left - rect.left) * k, y: (b.top - rect.top) * k, w: b.width * k, h: b.height * k } });
        }
      } catch (e) { photos = []; imgs = []; }   // a photo that can't be read: zoom the whole design instead
      var touched = [];
      function clear(el, prop, value) { touched.push([el, prop, el.style[prop]]); el.style[prop] = value; }
      var overlay, base = getComputedStyle(sp).backgroundColor;
      try {
        if (photos.length) {
          imgs.forEach(function (img) {
            clear(img, 'visibility', 'hidden');
            for (var el = img.parentNode; el && el !== sp.parentNode; el = el.parentNode) clear(el, 'background', 'transparent');
          });
        }
        await htmlToImage.toCanvas(sp, opts);          // first pass warms the font and image cache
        overlay = await htmlToImage.toCanvas(sp, opts);
      } finally { touched.reverse().forEach(function (t) { t[0].style[t[1]] = t[2]; }); }

      var out = document.createElement('canvas'); out.width = w; out.height = h;
      var ctx = out.getContext('2d');
      ctx.imageSmoothingQuality = 'high';
      function compose(p) {           // p: 0 → 1 over the video
        var z = ease(p);
        ctx.fillStyle = base && base !== 'rgba(0, 0, 0, 0)' ? base : '#FFF8EC';
        ctx.fillRect(0, 0, w, h);
        if (photos.length) {
          photos.forEach(function (ph, n) {
            ctx.save(); ctx.beginPath(); ctx.rect(ph.box.x, ph.box.y, ph.box.w, ph.box.h); ctx.clip();
            // alternate the drift direction when a design has two photos
            cover(ctx, ph.bmp, ph.box, 1 + 0.14 * z, n % 2 ? 0.5 - 0.08 * z : 0.5 + 0.08 * z, 0.5 - 0.06 * z);
            ctx.restore();
          });
          ctx.drawImage(overlay, 0, 0);
        } else {
          // no photo: a gentle push-in on the whole design
          var s = 1 + 0.05 * z;
          ctx.drawImage(overlay, (w - w * s) / 2, (h - h * s) / 2, w * s, h * s);
        }
      }

      var FPS = 30, N = Math.round(seconds * FPS);
      var config = { codec: 'avc1.640032', width: w, height: h, bitrate: 6000000, framerate: FPS };
      var ok = await VideoEncoder.isConfigSupported(config).then(function (r) { return r.supported; }).catch(function () { return false; });
      if (!ok) { config.codec = 'avc1.42003e'; ok = await VideoEncoder.isConfigSupported(config).then(function (r) { return r.supported; }).catch(function () { return false; }); }
      if (!ok) throw new Error('This browser has no H.264 video encoder. Use Chrome or Edge.');
      var muxer = new Mp4Muxer.Muxer({ target: new Mp4Muxer.ArrayBufferTarget(), video: { codec: 'avc', width: w, height: h }, fastStart: 'in-memory' });
      var failed = null;
      var enc = new VideoEncoder({ output: function (chunk, meta) { muxer.addVideoChunk(chunk, meta); }, error: function (e) { failed = e; } });
      enc.configure(config);
      for (var f = 0; f < N; f++) {
        if (failed) throw failed;
        compose(f / (N - 1));
        var vf = new VideoFrame(out, { timestamp: Math.round(f * 1e6 / FPS), duration: Math.round(1e6 / FPS) });
        enc.encode(vf, { keyFrame: f % FPS === 0 }); vf.close();
        if (enc.encodeQueueSize > 8) await new Promise(function (r) { setTimeout(r, 5); });
        if (onProgress) onProgress((f + 1) / N);
        if (f % 10 === 0) await new Promise(function (r) { setTimeout(r, 0); });
      }
      await enc.flush(); enc.close();
      if (failed) throw failed;
      muxer.finalize();
      return { blob: new Blob([muxer.target.buffer], { type: 'video/mp4' }), type: 'video/mp4', ext: 'mp4' };
    }
  };
})();
