(function () {
  var themeSegments = document.querySelectorAll('.theme-seg');
  function applyTheme(value) {
    document.documentElement.setAttribute('data-theme', value);
    localStorage.setItem('dk-theme', value);
    themeSegments.forEach(function (seg) {
      seg.classList.toggle('active', seg.getAttribute('data-theme-value') === value);
    });
  }
  themeSegments.forEach(function (seg) {
    seg.addEventListener('click', function () {
      applyTheme(seg.getAttribute('data-theme-value'));
    });
  });
  applyTheme(localStorage.getItem('dk-theme') || 'system');
})();
