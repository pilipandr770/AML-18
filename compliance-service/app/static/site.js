(function () {
  var de = document.documentElement.lang === "de";

  // scroll reveal
  var els = document.querySelectorAll(".rv");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (en) {
      en.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { threshold: 0.12 });
    els.forEach(function (e) { io.observe(e); });
  } else els.forEach(function (e) { e.classList.add("in"); });

  // example-response switcher
  document.querySelectorAll("[data-demo]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll("[data-demo]").forEach(function (b) { b.classList.remove("btn-p"); b.classList.add("btn-g"); });
      btn.classList.remove("btn-g"); btn.classList.add("btn-p");
      document.querySelectorAll("[data-demo-pane]").forEach(function (p) { p.hidden = p.getAttribute("data-demo-pane") !== btn.getAttribute("data-demo"); });
    });
  });

  // assistant widget
  var fab = document.getElementById("chat-fab"), box = document.getElementById("chat");
  if (!fab || !box) return;
  var log = document.getElementById("chat-log"), form = document.getElementById("chat-form"), input = document.getElementById("chat-input"), chips = document.getElementById("chat-chips");
  var history = [], busy = false;
  function add(role, text) {
    var d = document.createElement("div"); d.className = "msg " + (role === "user" ? "me" : "bot"); d.textContent = text;
    log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
  }
  function open(on) { box.classList.toggle("open", on); if (on) { input.focus(); if (!log.children.length) add("assistant", box.getAttribute("data-hello")); } }
  fab.addEventListener("click", function () { open(!box.classList.contains("open")); });
  document.getElementById("chat-close").addEventListener("click", function () { open(false); });
  document.querySelectorAll("[data-open-chat]").forEach(function (b) { b.addEventListener("click", function (e) { e.preventDefault(); open(true); }); });
  function ask(q) {
    if (busy || !q.trim()) return;
    busy = true; chips.style.display = "none";
    add("user", q); history.push({ role: "user", content: q });
    var wait = add("assistant", "…");
    fetch("/assistant/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages: history.slice(-8) }) })
      .then(function (r) { return r.json(); })
      .then(function (j) { var t = j.reply || j.error || "…"; wait.textContent = t; if (j.reply) history.push({ role: "assistant", content: t }); })
      .catch(function () { wait.textContent = de ? "Verbindung fehlgeschlagen." : "Connection failed."; })
      .then(function () { busy = false; log.scrollTop = log.scrollHeight; });
  }
  form.addEventListener("submit", function (e) { e.preventDefault(); var q = input.value; input.value = ""; ask(q); });
  chips.querySelectorAll("button").forEach(function (b) { b.addEventListener("click", function () { ask(b.textContent); }); });
})();
