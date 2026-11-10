// Hell/Dunkel-Schalter: merkt sich die Wahl im Browser, sonst gilt die Systemeinstellung.
(function () {
  var KEY = 'tbbn-theme';
  var root = document.documentElement;
  function stored() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function save(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  function apply(theme) {
    root.setAttribute('data-theme', theme);
    var btn = document.querySelector('.theme-toggle');
    if (btn) {
      var dark = theme === 'dark';
      btn.setAttribute('aria-pressed', String(dark));
      btn.setAttribute('aria-label', dark ? 'Hellen Modus aktivieren' : 'Dunklen Modus aktivieren');
      btn.title = dark ? 'Heller Modus' : 'Dunkler Modus';
    }
  }
  apply(root.getAttribute('data-theme') || 'light');
  var btn = document.querySelector('.theme-toggle');
  if (btn) btn.addEventListener('click', function () {
    var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    save(next); apply(next);
  });
  if (window.matchMedia) {
    var mq = window.matchMedia('(prefers-color-scheme: dark)');
    var follow = function (e) { if (!stored()) apply(e.matches ? 'dark' : 'light'); };
    if (mq.addEventListener) mq.addEventListener('change', follow); else if (mq.addListener) mq.addListener(follow);
  }
})();
