/* AML+18 hero: a 3D "transfer network". Cyan nodes are ordinary wallets, red ones are sanctioned. The whole graph
   follows the cursor; nodes near the pointer swell and light up, and a screening pulse sweeps outward from them. */
(function () {
  var canvas = document.getElementById("hero3d");
  if (!canvas || !window.THREE) return;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var small = window.innerWidth < 760;
  var renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: !small, alpha: true }); } catch (e) { return; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, small ? 1.5 : 2));

  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100);
  camera.position.z = 13;
  var group = new THREE.Group();
  scene.add(group);

  var N = small ? 110 : 230, FLAGGED = small ? 6 : 11;
  var base = new Float32Array(N * 3), pos = new Float32Array(N * 3), col = new Float32Array(N * 3);
  var flagged = [], i;
  for (i = 0; i < N; i++) {
    // points on a thick shell with a few strays inside, golden-angle spiral for even spread
    var k = i + 0.5, phi = Math.acos(1 - 2 * k / N), th = Math.PI * (1 + Math.sqrt(5)) * k;
    var r = 6.2 * (0.78 + Math.random() * 0.4);
    base[i * 3] = r * Math.cos(th) * Math.sin(phi);
    base[i * 3 + 1] = r * Math.sin(th) * Math.sin(phi) * 0.82;
    base[i * 3 + 2] = r * Math.cos(phi);
  }
  for (i = 0; i < FLAGGED; i++) flagged.push(Math.floor(Math.random() * N));
  var isFlag = {}; flagged.forEach(function (f) { isFlag[f] = true; });
  var CYAN = new THREE.Color("#5eead4"), BLUE = new THREE.Color("#60a5fa"), RED = new THREE.Color("#fb7185"), WHITE = new THREE.Color("#ffffff");
  var baseCol = [];
  for (i = 0; i < N; i++) baseCol.push(isFlag[i] ? RED : (Math.random() < 0.5 ? CYAN : BLUE));

  // edges: connect each node to its 2-3 nearest neighbours
  var edges = [];
  for (i = 0; i < N; i++) {
    var best = [];
    for (var j = 0; j < N; j++) {
      if (j === i) continue;
      var dx = base[i * 3] - base[j * 3], dy = base[i * 3 + 1] - base[j * 3 + 1], dz = base[i * 3 + 2] - base[j * 3 + 2];
      best.push([dx * dx + dy * dy + dz * dz, j]);
    }
    best.sort(function (a, b) { return a[0] - b[0]; });
    for (var m = 0; m < 2; m++) if (i < best[m][1]) edges.push([i, best[m][1]]);
  }
  var linePos = new Float32Array(edges.length * 6), lineCol = new Float32Array(edges.length * 6);
  var lg = new THREE.BufferGeometry();
  lg.setAttribute("position", new THREE.BufferAttribute(linePos, 3));
  lg.setAttribute("color", new THREE.BufferAttribute(lineCol, 3));
  group.add(new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false })));

  var pg = new THREE.BufferGeometry();
  pg.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  pg.setAttribute("color", new THREE.BufferAttribute(col, 3));
  var sprite = (function () {
    var c = document.createElement("canvas"); c.width = c.height = 64;
    var x = c.getContext("2d"), g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.35, "rgba(255,255,255,.85)"); g.addColorStop(1, "rgba(255,255,255,0)");
    x.fillStyle = g; x.fillRect(0, 0, 64, 64);
    return new THREE.CanvasTexture(c);
  })();
  group.add(new THREE.Points(pg, new THREE.PointsMaterial({ size: small ? 0.6 : 0.5, map: sprite, vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true })));

  var mouse = { x: 9, y: 9, tx: 0, ty: 0 }, rotX = 0, rotY = 0, v = new THREE.Vector3(), t0 = performance.now(), running = true;
  function resize() {
    var w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false); camera.aspect = w / h;
    camera.position.x = w > 900 ? -3.6 : 0; // keep the graph clear of the headline on wide screens
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize); resize();
  function point(e) {
    var rect = canvas.getBoundingClientRect(), p = e.touches ? e.touches[0] : e;
    mouse.x = ((p.clientX - rect.left) / rect.width) * 2 - 1; mouse.y = -((p.clientY - rect.top) / rect.height) * 2 + 1;
    mouse.tx = mouse.x; mouse.ty = mouse.y;
  }
  window.addEventListener("pointermove", point, { passive: true });
  window.addEventListener("touchmove", point, { passive: true });
  window.addEventListener("pointerleave", function () { mouse.x = mouse.y = 9; });

  function frame(now) {
    if (!running) return;
    requestAnimationFrame(frame);
    var t = (now - t0) / 1000;
    var aimY = reduce ? 0 : t * 0.07 + mouse.tx * 0.55, aimX = reduce ? 0 : mouse.ty * -0.35;
    rotY += (aimY - rotY) * 0.04; rotX += (aimX - rotX) * 0.04;
    group.rotation.set(rotX, rotY, 0);
    group.updateMatrixWorld(true);
    var pulse = (t % 3.2) / 3.2;
    for (var n = 0; n < N; n++) {
      var bx = base[n * 3], by = base[n * 3 + 1], bz = base[n * 3 + 2];
      v.set(bx, by, bz).applyMatrix4(group.matrixWorld).project(camera);
      var dx = v.x - mouse.x, dy = (v.y - mouse.y) * (canvas.clientHeight / canvas.clientWidth), d = Math.sqrt(dx * dx + dy * dy);
      var f = Math.max(0, 1 - d / 0.36); f = f * f;
      var s = 1 + f * 0.32 + (isFlag[n] ? 0.05 * Math.sin(t * 3 + n) : 0);
      pos[n * 3] = bx * s; pos[n * 3 + 1] = by * s; pos[n * 3 + 2] = bz * s;
      var c = baseCol[n], glow = f + (isFlag[n] ? 0.25 + 0.25 * Math.sin(t * 3 + n) : 0);
      var wave = Math.max(0, 1 - Math.abs(Math.sqrt(bx * bx + by * by + bz * bz) / 8 - pulse) * 9) * 0.35;
      col[n * 3] = c.r + (WHITE.r - c.r) * Math.min(1, glow * 0.7) + wave * 0.3;
      col[n * 3 + 1] = c.g + (WHITE.g - c.g) * Math.min(1, glow * 0.7) + wave * 0.3;
      col[n * 3 + 2] = c.b + (WHITE.b - c.b) * Math.min(1, glow * 0.7) + wave * 0.3;
    }
    for (var e = 0; e < edges.length; e++) {
      var a = edges[e][0], b = edges[e][1], q = e * 6;
      linePos[q] = pos[a * 3]; linePos[q + 1] = pos[a * 3 + 1]; linePos[q + 2] = pos[a * 3 + 2];
      linePos[q + 3] = pos[b * 3]; linePos[q + 4] = pos[b * 3 + 1]; linePos[q + 5] = pos[b * 3 + 2];
      var red = isFlag[a] || isFlag[b], k2 = red ? 1.0 : 0.42;
      lineCol[q] = lineCol[q + 3] = red ? 0.98 * k2 : 0.37 * k2; lineCol[q + 1] = lineCol[q + 4] = red ? 0.44 * k2 : 0.92 * k2; lineCol[q + 2] = lineCol[q + 5] = red ? 0.52 * k2 : 0.83 * k2;
    }
    pg.attributes.position.needsUpdate = pg.attributes.color.needsUpdate = true;
    lg.attributes.position.needsUpdate = lg.attributes.color.needsUpdate = true;
    renderer.render(scene, camera);
  }
  requestAnimationFrame(frame);
  // stop rendering when the hero is off screen or the tab is hidden
  function setRunning(on) { if (on && !running) { running = true; requestAnimationFrame(frame); } else if (!on) running = false; }
  if ("IntersectionObserver" in window) new IntersectionObserver(function (en) { setRunning(en[0].isIntersecting); }).observe(canvas);
  document.addEventListener("visibilitychange", function () { setRunning(!document.hidden); });
})();
