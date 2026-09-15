const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  const hamburgerBtn = document.getElementById('hamburgerBtn');

  function openSidebar() {
    sidebar.classList.add('show');
    overlay.classList.add('show');
    hamburgerBtn.innerHTML = '<i class="bi bi-x-lg"></i>';
  }

  function closeSidebar() {
    sidebar.classList.remove('show');
    overlay.classList.remove('show');
    hamburgerBtn.innerHTML = '<i class="bi bi-list"></i>';
  }

  hamburgerBtn.addEventListener('click', () => {
    sidebar.classList.contains('show') ? closeSidebar() : openSidebar();
  });

  overlay.addEventListener('click', closeSidebar);

  // Cerrar sidebar en mobile al hacer click en enlace
  document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth < 992) {
        closeSidebar();
      }
    });
  });

  // Al redimensionar a desktop, limpiar estado mobile
  window.addEventListener('resize', () => {
    if (window.innerWidth >= 992) {
      sidebar.classList.remove('show');
      overlay.classList.remove('show');
      hamburgerBtn.innerHTML = '<i class="bi bi-list"></i>';
    }
  });

// ===== FORMATO MONEDA COLOMBIANA (price-cop) =====
(function() {
  function formatCOP(val) {
    const digits = String(val).replace(/\D/g, '');
    if (!digits) return '';
    return parseInt(digits, 10).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  // Exponer globalmente para uso en otros scripts
  window.formatCOP = formatCOP;
  window.parseCOP = function(val) {
    return parseFloat(String(val).replace(/\./g, '')) || 0;
  };

  function initPriceCOP(input) {
    if (input.dataset.copInit) return;
    input.dataset.copInit = '1';
    input.type = 'text';
    input.inputMode = 'numeric';
    if (input.value) input.value = formatCOP(input.value);

    input.addEventListener('input', function() {
      const cursor = this.selectionStart;
      const oldLen = this.value.length;
      const formatted = formatCOP(this.value);
      this.value = formatted;
      const diff = formatted.length - oldLen;
      this.selectionStart = this.selectionEnd = Math.max(0, cursor + diff);
    });

    input.addEventListener('paste', function(e) {
      e.preventDefault();
      const pasted = (e.clipboardData || window.clipboardData).getData('text');
      this.value = formatCOP(pasted);
    });
  }

  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('input.price-cop').forEach(initPriceCOP);

    // También inicializar entradas que se añadan dinámicamente (ej: formsets)
    const observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        mutation.addedNodes.forEach(function(node) {
          if (node.nodeType === 1) {
            node.querySelectorAll && node.querySelectorAll('input.price-cop').forEach(initPriceCOP);
            if (node.matches && node.matches('input.price-cop')) initPriceCOP(node);
          }
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // Limpiar puntos antes de enviar formularios
    document.querySelectorAll('form').forEach(function(form) {
      form.addEventListener('submit', function() {
        form.querySelectorAll('input.price-cop').forEach(function(input) {
          input.value = input.value.replace(/\./g, '');
        });
      }, true);
    });
  });
}());
