/* The waving Maldivian flag for the "National day" social template, and recording it as a video.
 * Flag geometry: the standard 720 x 480 layout (red #D21034, green panel #007E3A, white crescent opening to the fly). */
(function () {
  var FW = 860, FH = 573, PAD = 70, X0 = 26, POLE = 14;   // canvas is (FW + 40) x (FH + 2 PAD)
  var src = null;

  function flagArt() {
    if (src) return src;
    src = document.createElement('canvas'); src.width = FW; src.height = FH;
    var g = src.getContext('2d'), k = FW / 720;
    g.fillStyle = '#D21034'; g.fillRect(0, 0, FW, FH);
    g.fillStyle = '#007E3A'; g.fillRect(180 * k, 120 * k, 360 * k, 240 * k);
    g.fillStyle = '#fff'; g.beginPath(); g.arc(410 * k, 240 * k, 80 * k, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#007E3A'; g.beginPath(); g.arc(440 * k, 240 * k, 80 * k, 0, Math.PI * 2); g.fill();
    return src;
  }

  // Draw one moment of the wave. t in [0, 1) is one full wave; the pattern repeats every 1.
  function draw(ctx, t, ox, oy) {
    ox = ox || 0; oy = oy || 0;
    var art = flagArt();
    var pg = ctx.createLinearGradient(ox + X0 - POLE, 0, ox + X0, 0);
    pg.addColorStop(0, '#4A6068'); pg.addColorStop(0.5, '#DCE6E8'); pg.addColorStop(1, '#7D9399');
    ctx.fillStyle = pg; ctx.fillRect(ox + X0 - POLE, oy + 10, POLE, FH + PAD * 2 - 10);
    for (var x = 0; x < FW; x++) {
      var f = x / FW, amp = 6 + 34 * f, ph = 2 * Math.PI * (2.1 * f - t);
      var dy = amp * Math.sin(ph) + 8 * f * Math.sin(2 * Math.PI * (1.3 * f - 2 * t));
      var shade = Math.cos(ph) * 0.15 * (0.35 + f);
      ctx.drawImage(art, x, 0, 1, FH, ox + X0 + x, oy + PAD + dy, 1, FH);
      ctx.fillStyle = shade > 0 ? 'rgba(255,255,255,' + shade.toFixed(3) + ')' : 'rgba(0,0,0,' + (-shade * 0.9).toFixed(3) + ')';
      ctx.fillRect(ox + X0 + x, oy + PAD + dy, 1, FH);
    }
  }

  function paint(cv, t) { var c = cv.getContext('2d'); c.clearRect(0, 0, cv.width, cv.height); draw(c, t); }

  // Every flag canvas on the page waves gently; a still frame is used while exporting images.
  var running = true, start = performance.now();
  function frame(now) {
    var t = ((now - start) / 4000) % 1;
    document.querySelectorAll('canvas[data-flag]').forEach(function (cv) { if (running) paint(cv, t); });
    requestAnimationFrame(frame);
  }
  function init() {
    document.querySelectorAll('canvas[data-flag]').forEach(function (cv) { paint(cv, 0); });
    if (!window.matchMedia || !matchMedia('(prefers-reduced-motion: reduce)').matches) requestAnimationFrame(frame);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
  // New designs (e.g. the live preview) are painted on the next frame automatically; this paints them at once.
  window.IslandFlag = {
    paintAll: function () { document.querySelectorAll('canvas[data-flag]').forEach(function (cv) { paint(cv, 0); }); },
    pause: function () { running = false; document.querySelectorAll('canvas[data-flag]').forEach(function (cv) { paint(cv, 0); }); },
    resume: function () { running = true; },

    /* Record `seconds` of the design `sp` (a .sp element) with the flag waving. Resolves to {blob, type, ext}.
       Needs html-to-image (htmlToImage) on the page. The loop is seamless: the wave repeats every 4 seconds. */
    record: async function (sp, seconds, onProgress) {
      var flagCv = sp.querySelector('canvas[data-flag]');
      if (!flagCv) throw new Error('This design has no flag.');
      var w = +sp.dataset.w, h = +sp.dataset.h;
      var types = ['video/mp4;codecs=avc1.640028', 'video/mp4;codecs=avc1', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm'];
      var type = types.find(function (t) { return window.MediaRecorder && MediaRecorder.isTypeSupported(t); });
      if (!type && !window.VideoEncoder) throw new Error('This browser cannot make video. Try Chrome or Safari.');
      // 1. the design without the flag, as a still background
      running = false;
      var spRect = sp.getBoundingClientRect(), fRect = flagCv.getBoundingClientRect(), k = w / spRect.width;
      var fx = (fRect.left - spRect.left) * k, fy = (fRect.top - spRect.top) * k, fw = fRect.width * k, fh = fRect.height * k;
      flagCv.style.visibility = 'hidden';
      var bg;
      try {
        await document.fonts.ready;
        var opts = { width: w, height: h, pixelRatio: 1, style: { transform: 'none' } };
        await htmlToImage.toCanvas(sp, opts);
        bg = await htmlToImage.toCanvas(sp, opts);
      } finally { flagCv.style.visibility = ''; running = true; }
      var out = document.createElement('canvas'); out.width = w; out.height = h;
      var octx = out.getContext('2d');
      var flag = document.createElement('canvas'); flag.width = flagCv.width; flag.height = flagCv.height;
      function compose(t) {
        paint(flag, t % 1);
        octx.drawImage(bg, 0, 0);
        octx.save(); octx.filter = 'drop-shadow(0 26px 30px rgba(10,61,76,.22))';
        octx.drawImage(flag, fx, fy, fw, fh); octx.restore();
      }
      var FPS = 30, N = Math.round(seconds * FPS);
      // 2a. Preferred: encode frame by frame (smooth 30 fps on any computer) with the browser's H.264 encoder.
      if (window.VideoEncoder && window.Mp4Muxer) {
        var config = { codec: 'avc1.640032', width: w, height: h, bitrate: 6000000, framerate: FPS };
        var ok = await VideoEncoder.isConfigSupported(config).then(function (r) { return r.supported; }).catch(function () { return false; });
        if (ok) {
          var muxer = new Mp4Muxer.Muxer({ target: new Mp4Muxer.ArrayBufferTarget(), video: { codec: 'avc', width: w, height: h }, fastStart: 'in-memory' });
          var failed = null;
          var enc = new VideoEncoder({ output: function (chunk, meta) { muxer.addVideoChunk(chunk, meta); }, error: function (e) { failed = e; } });
          enc.configure(config);
          for (var i = 0; i < N; i++) {
            if (failed) throw failed;
            compose(i / FPS / 4);   // one wave every 4 seconds, so 8 s loops seamlessly
            var vf = new VideoFrame(out, { timestamp: Math.round(i * 1e6 / FPS), duration: Math.round(1e6 / FPS) });
            enc.encode(vf, { keyFrame: i % FPS === 0 }); vf.close();
            if (enc.encodeQueueSize > 8) await new Promise(function (r) { setTimeout(r, 5); });
            if (onProgress) onProgress((i + 1) / N);
            if (i % 10 === 0) await new Promise(function (r) { setTimeout(r, 0); });  // keep the page responsive
          }
          await enc.flush(); enc.close();
          if (failed) throw failed;
          muxer.finalize();
          return { blob: new Blob([muxer.target.buffer], { type: 'video/mp4' }), type: 'video/mp4', ext: 'mp4' };
        }
      }
      // 2b. Fallback: record the canvas in real time.
      var stream = out.captureStream(FPS);
      var rec = new MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: 8000000 });
      var chunks = [];
      rec.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
      var done = new Promise(function (resolve) { rec.onstop = resolve; });
      var t0 = performance.now(), total = seconds * 1000;
      function tick(now) {
        var el = now - t0;
        compose(el / 4000);
        if (onProgress) onProgress(Math.min(1, el / total));
        if (el < total) requestAnimationFrame(tick); else rec.stop();
      }
      rec.start(250);
      requestAnimationFrame(tick);
      await done;
      stream.getTracks().forEach(function (tr) { tr.stop(); });
      var blob = new Blob(chunks, { type: type.split(';')[0] });
      return { blob: blob, type: type, ext: type.indexOf('mp4') >= 0 ? 'mp4' : 'webm' };
    }
  };
})();
