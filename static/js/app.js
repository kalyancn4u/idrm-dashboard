/* =========================================================================
   IDRM — client behaviour
   Deliberately dependency-free. Everything degrades gracefully.
   ========================================================================= */
(function () {
  'use strict';

  /* ---------------------------------------------------- Sidebar toggle ---- */
  function initSidebar() {
    const shell = document.getElementById('appShell');
    const toggle = document.querySelector('[data-sidebar-toggle]');
    if (!shell || !toggle) return;

    toggle.addEventListener('click', function () {
      const open = shell.classList.toggle('sidebar-open');
      toggle.setAttribute('aria-expanded', String(open));
    });

    // Close on Escape
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && shell.classList.contains('sidebar-open')) {
        shell.classList.remove('sidebar-open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });

    // Close when clicking outside on small screens
    document.addEventListener('click', function (e) {
      if (window.innerWidth > 1024) return;
      if (!shell.classList.contains('sidebar-open')) return;
      if (shell.contains(e.target) && !e.target.closest('.app-sidebar')) {
        shell.classList.remove('sidebar-open');
      }
    });
  }

  /* ------------------------------------------------------- Confirm forms -- */
  function initConfirms() {
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        if (!window.confirm(form.dataset.confirm)) {
          e.preventDefault();
        }
      });
    });
  }

  /* --------------------------------------------------- Double-submit lock - */
  function initSubmitLock() {
    document.querySelectorAll('form').forEach(function (form) {
      form.addEventListener('submit', function () {
        if (form.dataset.noLock) return;
        const btn = form.querySelector('button[type="submit"]');
        if (!btn || btn.disabled) return;
        btn.dataset.originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Working…';
        // Re-enable if navigation is cancelled (e.g. confirm dialog)
        setTimeout(function () {
          if (btn.disabled) {
            btn.disabled = false;
            btn.textContent = btn.dataset.originalText || 'Submit';
          }
        }, 8000);
      });
    });
  }

  /* ------------------------------------------------------ Auto-dismiss ---- */
  function initFlashDismiss() {
    document.querySelectorAll('.flash-stack .alert-success').forEach(function (el) {
      setTimeout(function () {
        el.style.transition = 'opacity .4s ease, transform .4s ease';
        el.style.opacity = '0';
        el.style.transform = 'translateY(-6px)';
        setTimeout(function () { el.remove(); }, 420);
      }, 5000);
    });
  }

  /* ----------------------------------------------------- Filter autosubmit  */
  function initFilterAuto() {
    document.querySelectorAll('.filter-bar select').forEach(function (sel) {
      sel.addEventListener('change', function () {
        const form = sel.closest('form');
        if (form && form.dataset.autoSubmit === 'true') form.submit();
      });
    });
  }

  /* ------------------------------------------------------- Keyboard help -- */
  function initShortcuts() {
    document.addEventListener('keydown', function (e) {
      // "/" focuses the first search input
      if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
        const input = document.querySelector('.filter-bar input[type="text"], .filter-bar input[type="search"]');
        if (input) {
          e.preventDefault();
          input.focus();
        }
      }
    });
  }

  /* ------------------------------------------------------------ Boot ----- */
  function boot() {
    initSidebar();
    initConfirms();
    initSubmitLock();
    initFlashDismiss();
    initFilterAuto();
    initShortcuts();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
