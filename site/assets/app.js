// Edge Inference Handbook — interactions (no dependencies)
(function () {
  'use strict';

  // ---- theme ----
  var root = document.documentElement;
  var stored = null;
  try { stored = localStorage.getItem('eih-theme'); } catch (e) {}
  var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  setTheme(stored || (prefersDark ? 'dark' : 'light'));

  function setTheme(t) {
    root.setAttribute('data-theme', t);
    try { localStorage.setItem('eih-theme', t); } catch (e) {}
    var btn = document.getElementById('theme-btn');
    if (btn) btn.setAttribute('aria-label', t === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  }

  document.addEventListener('click', function (e) {
    var tb = e.target.closest && e.target.closest('#theme-btn');
    if (tb) { setTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'); }

    var mb = e.target.closest && e.target.closest('#menu-btn');
    if (mb) { document.body.classList.toggle('nav-open'); }

    if (e.target.closest && e.target.closest('.backdrop')) { document.body.classList.remove('nav-open'); }

    var rl = e.target.closest && e.target.closest('.rail a');
    if (rl) { document.body.classList.remove('nav-open'); }

    var cp = e.target.closest && e.target.closest('.cb-copy');
    if (cp) { copyCode(cp); }
  });

  function copyCode(btn) {
    var block = btn.closest('.codeblock');
    var pre = block && block.querySelector('pre');
    if (!pre) return;
    var text = pre.innerText;
    navigator.clipboard.writeText(text).then(function () {
      var old = btn.textContent;
      btn.textContent = 'copied ✓'; btn.classList.add('done');
      setTimeout(function () { btn.textContent = old; btn.classList.remove('done'); }, 1400);
    });
  }

  // ---- reading progress ----
  var bar = document.getElementById('progress');
  function onScroll() {
    if (bar) {
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
    }
    spy();
  }
  window.addEventListener('scroll', onScroll, { passive: true });

  // ---- TOC scroll-spy ----
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('.toc a'));
  var targets = tocLinks.map(function (a) {
    var id = a.getAttribute('href').slice(1);
    return document.getElementById(id);
  });
  function spy() {
    if (!tocLinks.length) return;
    var pos = window.scrollY + 120;
    var idx = -1;
    for (var i = 0; i < targets.length; i++) {
      if (targets[i] && targets[i].offsetTop <= pos) idx = i;
    }
    tocLinks.forEach(function (a, i) { a.classList.toggle('active', i === idx); });
  }

  onScroll();
})();
