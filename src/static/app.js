(function () {
  var themeSegments = document.querySelectorAll('.theme-seg');
  var themeRadios = document.querySelectorAll('input[name="theme-choice"]');
  function applyTheme(value) {
    document.documentElement.setAttribute('data-theme', value);
    localStorage.setItem('dk-theme', value);
    themeSegments.forEach(function (seg) {
      seg.classList.toggle('active', seg.getAttribute('data-theme-value') === value);
    });
    themeRadios.forEach(function (radio) {
      radio.checked = radio.getAttribute('data-theme-value') === value;
    });
  }
  themeSegments.forEach(function (seg) {
    seg.addEventListener('click', function () {
      applyTheme(seg.getAttribute('data-theme-value'));
    });
  });
  themeRadios.forEach(function (radio) {
    radio.addEventListener('change', function () {
      if (radio.checked) { applyTheme(radio.getAttribute('data-theme-value')); }
    });
  });
  applyTheme(localStorage.getItem('dk-theme') || 'system');

  var privacyToggles = document.querySelectorAll('.privacy-toggle');
  function applyMask(on) {
    document.body.classList.toggle('hide-amounts', on);
    privacyToggles.forEach(function (btn) {
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      btn.classList.toggle('active', on);
    });
    document.querySelectorAll('.money').forEach(function (el) {
      if (!el.getAttribute('data-value')) {
        el.setAttribute('data-value', el.textContent);
      }
      el.textContent = on ? '₹••••••' : el.getAttribute('data-value');
    });
  }
  privacyToggles.forEach(function (btn) {
    btn.addEventListener('click', function () {
      applyMask(!document.body.classList.contains('hide-amounts'));
    });
  });
  var privacyStored = null;
  try {
    privacyStored = localStorage.getItem('privacy_mode');
  } catch (err) {
    privacyStored = null;
  }
  applyMask(privacyStored === 'on');
})();
