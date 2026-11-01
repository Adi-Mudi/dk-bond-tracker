(function () {
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

  var dashboardTabs = document.querySelectorAll('#dashboard-tabs .tab');
  var dpanelOverview = document.getElementById('dpanel-overview');
  var dpanelReturns = document.getElementById('dpanel-returns');
  function activateDashboardTab(name) {
    dashboardTabs.forEach(function (tab) {
      tab.classList.toggle('active', tab.getAttribute('data-dtab') === name);
    });
    if (dpanelOverview) {
      dpanelOverview.classList.toggle('active', name === 'overview');
    }
    if (dpanelReturns) {
      dpanelReturns.classList.toggle('active', name === 'returns');
    }
  }
  dashboardTabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      activateDashboardTab(tab.getAttribute('data-dtab'));
    });
  });
  if (window.location.hash === '#returns' && dpanelReturns) {
    activateDashboardTab('returns');
    if (dpanelReturns.scrollIntoView) {
      dpanelReturns.scrollIntoView();
    }
  }
  if (window.location.hash === '#returns' && document.body.getAttribute('data-page') !== '/') {
    window.location.replace('/#returns');
  }

  var filterChips = document.querySelectorAll('.filter-chip');
  filterChips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      filterChips.forEach(function (other) { other.classList.remove('active'); });
      chip.classList.add('active');
      var filter = chip.getAttribute('data-filter');
      document.querySelectorAll('.chart-row[data-status]').forEach(function (row) {
        row.hidden = filter !== 'all' && row.getAttribute('data-status') !== filter;
      });
    });
  });

  var emailPresets = {
    gmail: { host: 'smtp.gmail.com', port: '587', security: 'TLS' },
    outlook: { host: 'smtp.office365.com', port: '587', security: 'STARTTLS' },
    custom: { host: '', port: '', security: '' }
  };
  var providerSelect = document.getElementById('s-provider');
  if (providerSelect) {
    providerSelect.addEventListener('change', function () {
      var preset = emailPresets[providerSelect.value] || emailPresets.custom;
      document.getElementById('s-host').value = preset.host;
      document.getElementById('s-port').value = preset.port;
      document.getElementById('s-security').value = preset.security;
    });
  }

  var sendTestButton = document.getElementById('s-send-test');
  if (sendTestButton) {
    sendTestButton.addEventListener('click', function () {
      var banner = document.getElementById('email-test-banner');
      var settingsForm = document.getElementById('settings-form');
      var failureText = 'Sending failed. Authentication failed = usually needs an App Password. Also check SMTP host, port and security setting.';
      function showBanner(status, message) {
        banner.hidden = false;
        banner.className = 'test-banner ' + (status === 'success' ? 'banner-success' : 'banner-failure');
        banner.textContent = message;
      }
      fetch('/settings/email/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams(new FormData(settingsForm)).toString()
      })
        .then(function (response) { return response.json(); })
        .then(function (data) { showBanner(data.status, data.message); })
        .catch(function () { showBanner('failure', failureText); });
    });
  }
})();
