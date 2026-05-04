/**
 * registros.js
 * Lógica para pestañas, filtrado en tiempo real y modales.
 */

//  PESTAÑAS (TABS) 

function verTab(tabId) {
  // Ocultar todos los panes
  document.querySelectorAll('.tab-pane').forEach(pane => {
    pane.classList.remove('active');
  });
  // Desactivar todos los botones
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active');
  });

  // Activar el seleccionado
  document.getElementById(tabId).classList.add('active');
  
  // Buscar el botón correspondiente por el onclick
  const targetBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(tabId));
  if (targetBtn) targetBtn.classList.add('active');

  // Guardar en sessionStorage para persistir tras recarga (opcional)
  sessionStorage.setItem('activeTab', tabId);
}

// Persistencia de pestaña activa al recargar
document.addEventListener('DOMContentLoaded', () => {
  const savedTab = sessionStorage.getItem('activeTab');
  if (savedTab && document.getElementById(savedTab)) {
    verTab(savedTab);
  }

  // Inicializar Flatpickr (Selector de Fecha Enterprise)
  const inputFecha = document.getElementById('modal-fecha');
  if (inputFecha && typeof flatpickr !== 'undefined') {
    flatpickr(inputFecha, {
      enableTime: true,
      dateFormat: "Y-m-d\\TH:i",
      altInput: true,
      altFormat: "d/m/Y h:i K",
      locale: "es"
    });
  }
});


//  FILTRADO EN TIEMPO REAL 

function filtrarTablero() {
  const input = document.getElementById('dashboard-search');
  const query = input.value.toLowerCase().trim();
  const terms = query.split(/\s+/); // Soporta múltiples términos ej: "TCL #15"
  
  const rows = document.querySelectorAll('tr[data-search]');

  rows.forEach(row => {
    const text = row.getAttribute('data-search');
    // Debe contener todos los términos buscados
    const match = terms.every(term => text.includes(term));
    
    if (match) {
      row.classList.remove('hidden');
    } else {
      row.classList.add('hidden');
    }
  });

  actualizarContadoresVisibles();
}

function actualizarContadoresVisibles() {
  // Esta función podría usarse para actualizar los números de las pestañas 
  // basados en el filtrado, pero por ahora los dejamos estáticos del servidor.
}


//  MODAL RETIROS (Antiguo + Mejorado) 

function abrirModalRetiro(id, marca, tipo) {
  const esDirecto = tipo === 'directo';
  document.getElementById('modal-titulo').textContent =
    esDirecto ? ' Confirmar retiro directo' : ' Confirmar retiro';
  
  document.getElementById('modal-desc').textContent =
    `Pedido #${id} de ${marca}` + (esDirecto ? ' (Retiro sin empaque previo)' : '');
    
  document.getElementById('form-retiro').action = `/retirar/${id}`;
  document.getElementById('modal-persona').value = '';
  document.getElementById('modal-persona').style.borderColor = '';
  
  const btn = document.getElementById('btn-confirmar-retiro');
  if (esDirecto) { 
    btn.style.background = '#15803d'; 
    btn.style.color = '#fff'; 
  } else { 
    btn.style.background = ''; 
    btn.style.color = ''; 
  }
  
  // Manejo de bultos obligatorios si faltan
  const row = document.querySelector(`tr[data-id="${id}"]`);
  const bultosRaw = row ? row.querySelector('.bultos-badge')?.textContent.trim() : null;
  const tieneBultos = bultosRaw && bultosRaw !== '?' && bultosRaw !== '0' && bultosRaw !== '—';
  const groupBultos = document.getElementById('modal-group-bultos');
  const inputBultos = document.getElementById('modal-bultos');
  
  if (!tieneBultos) {
    groupBultos.style.display = 'block';
    inputBultos.required = true;
    inputBultos.value = '';
  } else {
    groupBultos.style.display = 'none';
    inputBultos.required = false;
  }

  document.getElementById('modal-retiro').classList.add('open');
  setTimeout(() => document.getElementById('modal-persona').focus(), 100);

  // Inicializar fecha actual en el input flatpickr
  const inputFecha = document.getElementById('modal-fecha');
  if (inputFecha) {
    const ahora = new Date();
    ahora.setMinutes(ahora.getMinutes() - ahora.getTimezoneOffset());
    const dateStr = ahora.toISOString().slice(0, 16);
    if (inputFecha._flatpickr) {
      inputFecha._flatpickr.setDate(dateStr);
    } else {
      inputFecha.value = dateStr;
    }
  }
}

function abrirModalEditarRetiro(data) {
  // data contiene: id, marca, persona, fecha
  document.getElementById('modal-titulo').textContent = ` Editar Retiro - #${data.id}`;
  document.getElementById('modal-desc').textContent = `Pedido de ${data.marca}`;
  
  document.getElementById('form-retiro').action = `/pedido/${data.id}/editar_retiro`;
  document.getElementById('modal-persona').value = data.persona || '';
  const inputFecha = document.getElementById('modal-fecha');
  if (inputFecha._flatpickr) {
    inputFecha._flatpickr.setDate(data.fecha || '');
  } else {
    inputFecha.value = data.fecha || '';
  }
  
  // En edición usualmente ya tienen bultos, ocultamos el grupo
  document.getElementById('modal-group-bultos').style.display = 'none';
  document.getElementById('modal-bultos').required = false;

  document.getElementById('modal-retiro').classList.add('open');
}

function cerrarModal() {
  document.getElementById('modal-retiro').classList.remove('open');
}

function confirmarRetiro() {
  const persona = document.getElementById('modal-persona').value.trim();
  if (!persona) {
    document.getElementById('modal-persona').focus();
    document.getElementById('modal-persona').style.borderColor = 'var(--danger)';
    return;
  }

  const inputBultos = document.getElementById('modal-bultos');
  if (inputBultos.required && !inputBultos.value) {
    inputBultos.focus();
    inputBultos.style.borderColor = 'var(--danger)';
    return;
  }

  document.getElementById('campo-retirado-por').value = persona;
  
  const inputFecha = document.getElementById('modal-fecha');
  if (inputFecha && inputFecha.value) {
    document.getElementById('campo-retirado-en').value = inputFecha.value;
  }

  document.getElementById('form-retiro').submit();
}

// Cerrar al clickear fuera
const modalRetiro = document.getElementById('modal-retiro');
if (modalRetiro) {
  modalRetiro.addEventListener('click', function(e) {
    if (e.target === this) cerrarModal();
  });
}

// Enter para confirmar en el input
const modalPersona = document.getElementById('modal-persona');
if (modalPersona) {
  modalPersona.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      confirmarRetiro();
    }
    this.style.borderColor = '';
  });
}

function confirmarEliminar(marca) {
  return confirm(
    `¿Mover el pedido de "${marca}" a la papelera?\n\n` +
    `No se borrará definitivamente, podrás restaurarlo si es necesario.`
  );
}

//  ACCIONES EN LOTE (BULK ACTIONS) 

function seleccionarTodo(tablaId, checked) {
  const table = document.getElementById(tablaId);
  const checkboxes = table.querySelectorAll('.row-checkbox');
  checkboxes.forEach(cb => {
    // Solo marcar los que no estén ocultos por el filtro
    const row = cb.closest('tr');
    if (!row.classList.contains('hidden')) {
      cb.checked = checked;
    }
  });
  actualizarBarraAcciones();
}

function actualizarBarraAcciones() {
  const selecionadas = document.querySelectorAll('.row-checkbox:checked');
  const bar = document.getElementById('batch-bar');
  const countSpan = document.getElementById('batch-count');
  
  if (selecionadas.length > 0) {
    countSpan.textContent = selecionadas.length;
    bar.classList.add('open');
  } else {
    bar.classList.remove('open');
    // Resetear "Select All" si todo está desmarcado
    document.getElementById('check-all-proceso').checked = false;
    document.getElementById('check-all-listos').checked = false;
  }
}

function limpiarSeleccion() {
  document.querySelectorAll('.row-checkbox').forEach(cb => cb.checked = false);
  document.getElementById('check-all-proceso').checked = false;
  document.getElementById('check-all-listos').checked = false;
  actualizarBarraAcciones();
}

function abrirRetiroMasivo() {
  const seleccionados = document.querySelectorAll('.row-checkbox:checked');
  const ids = Array.from(seleccionados).map(cb => cb.value);
  const marcas = Array.from(seleccionados).map(cb => cb.getAttribute('data-marca'));
  
  // Validar estados: Se permiten Directos en Pendiente o Empaque en Empacado
  let validos = true;
  seleccionados.forEach(cb => {
    const tipo = cb.getAttribute('data-tipo');
    const estado = cb.getAttribute('data-estado');
    if (tipo === 'empaque' && estado !== 'empacado') validos = false;
    // Directos se asume que se pueden retirar si están en proceso (pendiente)
  });
  
  if (!validos) {
    if (!confirm('Algunos pedidos seleccionados no han terminado su empaque. ¿Deseas continuar retirándolos de todos modos?')) {
      return;
    }
  }

  document.getElementById('modal-titulo').textContent = ` Retiro Masivo (${ids.length} pedidos)`;
  document.getElementById('modal-desc').textContent = `${marcas.slice(0, 3).join(', ')}${marcas.length > 3 ? '...' : ''}`;
  
  // Usaremos una ruta especial para el lote
  document.getElementById('form-retiro').action = `/retirar/batch`;
  
  // Inyectar los IDs en el form (necesitaremos un campo oculto)
  let inputIds = document.getElementById('batch-ids-input');
  if (!inputIds) {
    inputIds = document.createElement('input');
    inputIds.type = 'hidden';
    inputIds.name = 'ids';
    inputIds.id = 'batch-ids-input';
    document.getElementById('form-retiro').appendChild(inputIds);
  }
  inputIds.value = ids.join(',');

  document.getElementById('modal-persona').value = '';
  
  // Ocultar bultos en modo masivo (demasiado complejo para lote si faltan)
  document.getElementById('modal-group-bultos').style.display = 'none';
  document.getElementById('modal-bultos').required = false;

  document.getElementById('modal-retiro').classList.add('open');
  setTimeout(() => document.getElementById('modal-persona').focus(), 100);
  
  // Resetear fecha a ahora
  const inputFecha = document.getElementById('modal-fecha');
  if (inputFecha) {
    const ahora = new Date();
    ahora.setMinutes(ahora.getMinutes() - ahora.getTimezoneOffset());
    const dateStr = ahora.toISOString().slice(0, 16);
    if (inputFecha._flatpickr) {
      inputFecha._flatpickr.setDate(dateStr);
    } else {
      inputFecha.value = dateStr;
    }
  }
}
