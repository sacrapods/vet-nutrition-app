(function () {
  const APP_LOCALE = 'en-IN';
  function bySel(sel, root) { return (root || document).querySelector(sel); }
  function bySelAll(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }
  let lockedScrollY = 0;
  function lockBodyScroll() {
    lockedScrollY = window.scrollY || window.pageYOffset || 0;
    document.body.style.top = `-${lockedScrollY}px`;
    document.body.classList.add('modal-open', 'modal-open-lock');
  }
  function unlockBodyScroll() {
    const topStyle = document.body.style.top || '';
    const topOffset = topStyle ? Math.abs(parseInt(topStyle, 10) || 0) : null;
    document.body.classList.remove('modal-open', 'modal-open-lock');
    document.body.style.top = '';
    window.scrollTo(0, topOffset !== null ? topOffset : lockedScrollY);
  }
  function openModal(modal) {
    if (!modal) return;
    modal.classList.add('open');
    lockBodyScroll();
  }
  function closeModal(modal) {
    if (!modal) return;
    modal.classList.remove('open');
    if (!bySel('.modal.open')) {
      unlockBodyScroll();
    }
  }
  function initSidebarToggle() {
    const btn = bySel('[data-sidebar-toggle]');
    if (!btn) return;

    const key = 'petPortalNavCollapsed';
    const saved = window.localStorage.getItem(key);
    if (saved === '1') {
      document.body.classList.add('portal-nav-collapsed');
    }

    btn.addEventListener('click', function () {
      const collapsed = document.body.classList.toggle('portal-nav-collapsed');
      window.localStorage.setItem(key, collapsed ? '1' : '0');
    });
  }

  function enforceEnglishInputs() {
    bySelAll('input[type="date"], input[type="datetime-local"]').forEach(function (input) {
      input.setAttribute('lang', 'en-GB');
    });
  }

  function initModernFilePickers(root) {
    bySelAll('[data-file-picker]', root || document).forEach(function (picker) {
      if (picker.dataset.bound === '1') return;
      const input = bySel('input[type="file"]', picker);
      const nameNode = bySel('[data-file-name]', picker);
      if (!input || !nameNode) return;
      picker.dataset.bound = '1';
      const updateName = function () {
        const fileName = input.files && input.files.length ? input.files[0].name : '';
        nameNode.textContent = fileName || 'No file selected';
      };
      input.addEventListener('change', updateName);
      updateName();
    });
  }

  function initAutoDismissMessages(root) {
    bySelAll('.alert:not(.alert-undo), .upload-inline-success', root || document).forEach(function (node) {
      if (node.dataset.autoDismissBound === '1') return;
      node.dataset.autoDismissBound = '1';
      node.classList.add('auto-dismissable');
      window.setTimeout(function () {
        node.classList.add('is-dismissing');
        window.setTimeout(function () {
          if (node && node.parentNode) node.parentNode.removeChild(node);
        }, 240);
      }, 10000);
    });
  }

  document.addEventListener('change', function (event) {
    const input = event.target;
    if (!input || input.tagName !== 'INPUT' || input.type !== 'file') return;
    const picker = input.closest('[data-file-picker]');
    if (!picker) return;
    const nameNode = bySel('[data-file-name]', picker);
    if (!nameNode) return;
    const fileName = input.files && input.files.length ? input.files[0].name : '';
    nameNode.textContent = fileName || 'No file selected';
  });

  bySelAll('[data-toggle-dropdown]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const holder = btn.closest('.dropdown');
      holder.classList.toggle('open');
    });
  });

  bySelAll('[data-open-modal]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const id = btn.getAttribute('data-open-modal');
      const modal = bySel('#' + id);
      openModal(modal);
    });
  });

  bySelAll('[data-close-modal]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const modal = btn.closest('.modal');
      closeModal(modal);
    });
  });

  bySelAll('.modal').forEach(function (modal) {
    modal.addEventListener('click', function (e) {
      if (e.target === modal) closeModal(modal);
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    const activeModal = bySel('.modal.open');
    if (activeModal) closeModal(activeModal);
  });

  bySelAll('.ajax-form').forEach(function (form) {
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      const data = new FormData(form);
      const res = await fetch(form.action, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body: data,
      });
      if (res.ok) {
        window.location.reload();
        return;
      }
      let message = 'Could not save changes. Please validate fields.';
      try {
        const payload = await res.json();
        if (payload && payload.errors) {
          const flatten = [];
          Object.values(payload.errors).forEach(function (section) {
            if (Array.isArray(section)) {
              flatten.push.apply(flatten, section);
              return;
            }
            if (!section || typeof section !== 'object') return;
            Object.values(section).forEach(function (errs) {
              if (Array.isArray(errs)) flatten.push.apply(flatten, errs);
            });
          });
          if (flatten.length) message = flatten.join('\n');
        }
      } catch (err) {
        // keep fallback message
      }
      alert(message);
    });
  });

  bySelAll('.tab-link').forEach(function (btn) {
    btn.addEventListener('click', async function () {
      bySelAll('.tab-link').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');

      const tab = btn.getAttribute('data-tab');
      const parent = btn.getAttribute('data-parent');
      const pet = btn.getAttribute('data-pet');
      const hub = bySel('.profile-hub');
      const tabBaseUrl = hub ? hub.getAttribute('data-tab-url') : null;
      if (!tabBaseUrl) return;
      const url = `${tabBaseUrl}?tab=${encodeURIComponent(tab)}&pet=${encodeURIComponent(pet)}`;
      const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      if (!res.ok) return;
      const html = await res.text();
      const container = bySel('#tab-content');
      container.innerHTML = html;
      container.setAttribute('data-active-tab', tab);
      initCharts(container);
      initModernFilePickers(container);
      initAutoDismissMessages(container);
      window.history.replaceState({}, '', `?pet=${pet}&tab=${tab}`);
    });
  });

  function parsePoints(raw) {
    if (!raw) return [];
    try { return JSON.parse(raw); } catch (e1) {
      try { return Function('return (' + raw + ')')(); } catch (e2) { return []; }
    }
  }

  function initCharts(root) {
    bySelAll('canvas.chart', root || document).forEach(function (canvas) {
      const raw = canvas.getAttribute('data-points');
      const points = parsePoints(raw);
      if (!points.length) return;
      const allSameDay = points.length > 1 && points.every(function (p) {
        const d = new Date(p.x);
        return d.toDateString() === new Date(points[0].x).toDateString();
      });
      const labels = points.map(function (p) {
        const d = new Date(p.x);
        if (allSameDay) {
          return d.toLocaleTimeString(APP_LOCALE, { hour: '2-digit', minute: '2-digit' });
        }
        return d.toLocaleDateString(APP_LOCALE, { day: '2-digit', month: 'short' });
      });
      const values = points.map(function (p) { return p.y; });
      if (canvas._chartInstance) {
        canvas._chartInstance.destroy();
      }
      canvas._chartInstance = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
          labels: labels,
          datasets: [{
            data: values,
            borderColor: '#1a7bb2',
            backgroundColor: 'rgba(26,123,178,0.15)',
            borderWidth: 3,
            tension: 0.34,
            fill: true,
            pointRadius: 3,
            pointHoverRadius: 4,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { left: 6, right: 8, top: 4, bottom: 0 } },
          plugins: { legend: { display: false } },
          scales: {
            x: {
              type: 'category',
              ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 5 },
              grid: { color: 'rgba(21,36,49,0.08)' },
            },
            y: {
              beginAtZero: false,
              grace: '8%',
              grid: { color: 'rgba(21,36,49,0.08)' },
            },
          },
        },
      });
    });
  }

  initCharts(document);
  initSidebarToggle();
  enforceEnglishInputs();
  initModernFilePickers(document);
  initAutoDismissMessages(document);
})();
