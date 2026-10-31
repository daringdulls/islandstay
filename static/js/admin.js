/* Back office: text areas grow with their content so long text is easy to read and edit. */
(function () {
  function grow(t) { t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight + 2, 640) + 'px'; }
  function init() { document.querySelectorAll('textarea[data-autogrow]').forEach(function (t) { grow(t); }); }
  document.addEventListener('input', function (e) { if (e.target.matches && e.target.matches('textarea[data-autogrow]')) grow(e.target); });
  document.addEventListener('change', function (e) { if (e.target.matches && e.target.matches('textarea[data-autogrow]')) grow(e.target); });
  document.addEventListener('DOMContentLoaded', init);
  // Tabs hide fields until clicked: resize when one is opened.
  document.addEventListener('click', function () { setTimeout(init, 50); });
})();
