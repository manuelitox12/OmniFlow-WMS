/* 
   SISTEMA DE TOAST (notificaciones sin recarga)
 */
function showToast(msg, tipo = 'success') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;z-index:9999;display:flex;flex-direction:column;gap:.5rem;';
    document.body.appendChild(container);
  }
  const t = document.createElement('div');
  const colors = { success: '#16a34a', error: '#dc2626', info: '#0d2a6e' };
  t.style.cssText = `background:${colors[tipo]||colors.info};color:#fff;padding:.75rem 1.2rem;border-radius:8px;
                     font-size:.84rem;font-weight:600;box-shadow:0 4px 16px rgba(0,0,0,.25);
                     max-width:320px;animation:slideIn .2s ease;`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 300); }, 3500);
}

/* 
   NOMBRES DE SECCIONES
 */
const NOMBRES_SEC = ['Pasillo 1','Pasillo 2','Pasillo 3','Pasillo 4','2do Piso'];

function fmtHora(dt) {
  if (!dt) return '—';
  if (dt.length >= 16) {
    const mesNum = parseInt(dt.substring(5, 7), 10);
    const meses  = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
    const mesTxt = meses[mesNum - 1] || '???';
    const dd = dt.substring(8, 10);
    let hh = parseInt(dt.substring(11, 13), 10);
    const mm = dt.substring(14, 16);
    const ampm = hh >= 12 ? 'PM' : 'AM';
    hh = hh % 12;
    if (hh === 0) hh = 12;
    const hhStr = hh < 10 ? '0' + hh : hh;
    return `${dd} ${mesTxt} ${hhStr}:${mm} ${ampm}`;
  }
  return dt;
}

/* 
   ACTUALIZAR TARJETA DE SECCIÓN EN EL DOM
 */
/* 
   ACTUALIZAR TARJETA DE SECCIÓN EN EL DOM
 */
function actualizarTarjeta(uid, inicio, fin, persona) {
  const card = document.getElementById(`sec-card-${uid}`);
  if (!card) return;

  card.classList.remove('tiene-inicio', 'tiene-todo');
  if (inicio && fin)   card.classList.add('tiene-todo');
  else if (inicio)     card.classList.add('tiene-inicio');

  const iniSpan = document.getElementById(`sec-ini-${uid}`);
  const finSpan = document.getElementById(`sec-fin-${uid}`);
  if (iniSpan) { iniSpan.textContent = ` ${fmtHora(inicio)}`; iniSpan.className = `sec-time ${inicio ? 'inicio' : 'empty'}`; }
  if (finSpan) { finSpan.textContent = `⏹ ${fmtHora(fin)}`;    finSpan.className = `sec-time ${fin ? 'fin' : 'empty'}`; }

  const badge = document.getElementById(`sec-persona-badge-${uid}`);
  const txt   = document.getElementById(`sec-persona-txt-${uid}`);
  if (badge && txt) {
    txt.textContent = persona || 'Sin asignar';
    badge.style.color      = persona ? '#1d4ed8' : 'var(--muted)';
    badge.style.background = persona ? '#eff6ff' : 'var(--surface2)';
  }

  const btnIni     = document.getElementById(`btn-ini-${uid}`);
  const btnFin     = document.getElementById(`btn-fin-${uid}`);
  const btnLimpiar = document.getElementById(`btn-limpiar-${uid}`);
  if (btnIni)     btnIni.style.display     = inicio ? 'none' : '';
  if (btnFin)     btnFin.style.display     = (inicio && !fin) ? '' : 'none';
  if (btnLimpiar) btnLimpiar.style.display = (inicio || fin) ? '' : 'none';

  const mIni = document.getElementById(`sec-manual-ini-${uid}`);
  const mFin = document.getElementById(`sec-manual-fin-${uid}`);
  if (mIni && inicio) mIni.value = inicio.substring(0,16).replace(' ','T');
  if (mFin && fin)    mFin.value = fin.substring(0,16).replace(' ','T');
}

/* 
   REFRESCO / REDIBUJADO — necesario para las "partes" dinámicas
 */
async function refrescarSecciones() {
  const pedido_id = _getPedidoId();
  if (!pedido_id) return;
  try {
    // En vez de solo actualizar tarjetas, recargamos la página si hay cambios complejos,
    // o redibujamos el grid. Para simplicidad ahora que hay "partes", recargamos si 
    // detectamos que el número de registros cambió, o simplemente actualizamos las que existen.
    const res  = await fetch(`/api/pedido/${pedido_id}/secciones`);
    const data = await res.json();
    
    // Por ahora, solo actualizamos los campos de las tarjetas que ya están en el DOM.
    // Si queremos que se añadan dinámicamente, lo mejor es recargar la página.
    for (let n = 1; n <= 5; n++) {
      const parts = data[String(n)] || [];
      parts.forEach(sec => {
        actualizarTarjeta(sec.id, sec.inicio, sec.fin, sec.persona);
        const inp = document.getElementById(`sec-persona-input-${sec.id}`);
        if (inp && !inp.value && sec.persona) inp.value = sec.persona;
      });
    }
  } catch (e) {}
}

/* 
   ACCIONES RÁPIDAS "AHORA" — vía AJAX
 */
async function seccionAhora(pedido_id, sec_num, tipo_campo, record_id) {
  const uid = record_id && record_id !== 'None' ? record_id : `new-${sec_num}`;
  const persona = (document.getElementById(`sec-persona-input-${uid}`) || {}).value || '';
  await _guardarSeccion(pedido_id, sec_num, tipo_campo, 'now', persona, record_id);
}

async function seccionManual(pedido_id, sec_num, tipo_campo, record_id) {
  const uid = record_id && record_id !== 'None' ? record_id : `new-${sec_num}`;
  const inputId = tipo_campo === 'inicio' ? `sec-manual-ini-${uid}` : `sec-manual-fin-${uid}`;
  const valor   = (document.getElementById(inputId) || {}).value || 'now';
  const persona = (document.getElementById(`sec-persona-input-${uid}`) || {}).value || '';
  await _guardarSeccion(pedido_id, sec_num, tipo_campo, valor, persona, record_id);
}

async function actualizarPersona(uid, sec_num) {
  const persona   = (document.getElementById(`sec-persona-input-${uid}`) || {}).value || '';
  const iniSpan   = document.getElementById(`sec-ini-${uid}`);
  const hayInicio = iniSpan && !iniSpan.textContent.includes('—');
  const pedido_id = _getPedidoId();
  
  // Extraer record_id si el uid no empieza con 'new-'
  const record_id = uid.startsWith('new-') ? null : uid;

  if (hayInicio) {
    const mIni  = document.getElementById(`sec-manual-ini-${uid}`);
    const valor = mIni && mIni.value ? mIni.value : 'now';
    await _guardarSeccion(pedido_id, sec_num, 'inicio', valor, persona, record_id);
  } else {
    // Si no tiene inicio, solo intentamos guardar el nombre (requiere backend que acepte persona sola)
    await _guardarSeccion(pedido_id, sec_num, null, null, persona, record_id);
  }
}

async function dividirSeccion(pedido_id, sec_num) {
  try {
    const res = await fetch(`/api/pedido/${pedido_id}/seccion/${sec_num}/nueva`, { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      location.reload(); // Recargamos para que el Jinja dibuje la nueva card
    }
  } catch(e) { showToast('Error al dividir sección', 'error'); }
}

async function limpiarSeccion(pedido_id, sec_num, record_id) {
  if (!record_id || record_id === 'None') {
    showToast('No hay nada que limpiar', 'info');
    return;
  }
  if (!confirm(`¿Limpiar o eliminar esta parte de la sección ${sec_num}?`)) return;
  
  try {
    const res  = await fetch(`/api/seccion_record/${record_id}/limpiar`, { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      if (data.deleted) {
        location.reload(); 
      } else {
        actualizarTarjeta(record_id, null, null, null);
        const inp = document.getElementById(`sec-persona-input-${record_id}`);
        if (inp) inp.value = '';
        showToast(`↺ Sección ${sec_num} limpiada.`, 'info');
      }
    } else {
      showToast(data.msg || 'Error al limpiar', 'error');
    }
  } catch (e) {
    showToast('Error de red', 'error');
  }
}

async function _guardarSeccion(pedido_id, sec_num, tipo_campo, valor, persona, record_id) {
  try {
    let final_record_id = record_id;
    let isNew = (!record_id || record_id === 'None');

    // Si es nuevo (no tiene ID), primero creamos el registro en la DB 
    // para obtener un ID único y evitar sobrescribir a otros empleados
    if (isNew) {
      try {
        const resInit = await fetch(`/api/pedido/${pedido_id}/seccion/${sec_num}/nueva`, { method: 'POST' });
        const dataInit = await resInit.json();
        if (dataInit.ok) {
          final_record_id = dataInit.id;
        } else {
          showToast('Error al inicializar registro de pasillo', 'error');
          return;
        }
      } catch (e) {
        showToast('Error de conexión al inicializar pasillo', 'error');
        return;
      }
    }

    const url = `/api/seccion_record/${final_record_id}`;
    const res  = await fetch(url, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ tipo_campo, valor, persona })
    });
    const data = await res.json();
    if (data.ok) {
      if (isNew) {
        // En vez de recargar, actualizamos el DOM con el nuevo ID real
        const oldId = `new-${sec_num}`;
        const newId = data.id;
        _patchSectionCardIds(oldId, newId, sec_num);
        actualizarTarjeta(newId, data.inicio, data.fin, data.persona);
        showToast(` Pasillo inicializado y guardado.`, 'success');
      } else {
        actualizarTarjeta(data.id, data.inicio, data.fin, data.persona);
        showToast(` Sección — Guardado correctamente.`, 'success');
      }
    } else {
      showToast(data.msg || 'No se pudo guardar', 'error');
    }
  } catch (e) {
    showToast('Error de red al guardar', 'error');
  }
}

function _getPedidoId() {
  const m = window.location.pathname.match(/\/pedido\/(\d+)/);
  return m ? parseInt(m[1]) : null;
}

async function editarMarca() {
  const pedido_id = _getPedidoId();
  if (!pedido_id) return;
  const textoActual = document.getElementById('pedido-marca-texto').innerText;
  const nuevaMarca = prompt('Editar nombre / marca del pedido:', textoActual);
  if (nuevaMarca && nuevaMarca.trim() !== '' && nuevaMarca !== textoActual) {
    try {
      const res = await fetch(`/api/pedido/${pedido_id}/marca`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ marca: nuevaMarca.trim() })
      });
      const data = await res.json();
      if (data.ok) {
        document.getElementById('pedido-marca-texto').innerText = data.marca;
        document.title = document.title.replace(textoActual, data.marca);
        showToast('Nombre de pedido actualizado.', 'success');
      } else {
        showToast(data.msg || 'Error al actualizar', 'error');
      }
    } catch (e) {
      showToast('Error de red', 'error');
    }
  }
}

/* 
   OTRAS FUNCIONES
 */
function toggleAnexo(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

function toggleManual(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

function submitBulk(tipo) {
  const form = document.getElementById('form-bulk');
  const bulkTipo = document.getElementById('bulk-tipo');
  if (form && bulkTipo) {
    bulkTipo.value = tipo;
    form.submit();
  }
}

/**
 * Modo Preparación Global (Operador Único Real)
 */
async function reclamarPedidoGlobal() {
  const nombre = document.getElementById('operador-nombre').value.trim();
  if (!nombre) {
    showToast('Por favor, ingresa el nombre de quien prepara.', 'error');
    document.getElementById('operador-nombre').focus();
    return;
  }
  
  await actualizarPrepGlobal('inicio', 'now', nombre);
}

async function actualizarPrepGlobal(tipo, valor, persona = '') {
  const pId = _getPedidoId();
  if (!pId) {
    showToast('No se pudo identificar el ID del pedido.', 'error');
    return;
  }

  try {
    const response = await fetch(`/api/pedido/${pId}/preparacion_global`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tipo_campo: tipo, valor: valor, persona: persona })
    });
    
    console.log('API Response Status:', response.status);
    
    if (!response.ok) {
       const text = await response.text();
       console.error('API Error Response:', text);
       showToast(`Error del servidor (${response.status}).`, 'error');
       return;
    }

    const data = await response.json();
    if (data.ok) {
      showToast(' Preparación global actualizada.', 'info');
      window.location.reload();
    } else {
      showToast('Error al actualizar preparación global.', 'error');
    }
  } catch (error) {
    console.error('Fetch error:', error);
    showToast('Error de conexión o de red.', 'error');
  }
}

async function eliminarPreparacionGlobal() {
  if (!confirm('¿Estás seguro de eliminar el modo de preparación global? Esto volverá a habilitar la carga por pasillos individuales.')) return;
  
  await actualizarPrepGlobal('eliminar', '');
}

function rellenarDigitacionAhora() {
  const ahora = new Date();
  const pad   = n => String(n).padStart(2, '0');
  const val   = `${ahora.getFullYear()}-${pad(ahora.getMonth()+1)}-${pad(ahora.getDate())}T${pad(ahora.getHours())}:${pad(ahora.getMinutes())}`;
  const ini = document.querySelector('input[name="digitacion_inicio"]');
  const fin = document.querySelector('input[name="digitacion_fin"]');
  if (ini && !ini.value) ini.value = val;
  if (fin) fin.value = val;
}

/* Animación de toast */
const _style = document.createElement('style');
_style.textContent = '@keyframes slideIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}';
document.head.appendChild(_style);

/* 
   INFO-BAR STICKY: sombra al scrollear + botón flotante "↑ Pedido"
 */
(function() {
  const infoBar = document.querySelector('.info-bar');

  // Botón flotante para volver arriba
  const fab = document.createElement('button');
  fab.id = 'btn-volver-arriba';
  fab.innerHTML = '↑ Pedido';
  fab.style.cssText = [
    'position:fixed', 'bottom:1.5rem', 'left:1.5rem', 'z-index:999',
    'background:var(--navy)', 'color:var(--yellow)',
    'border:none', 'border-radius:20px',
    'padding:.45rem 1rem', 'font-size:.78rem', 'font-weight:700',
    'cursor:pointer', 'box-shadow:0 3px 12px rgba(13,42,110,.35)',
    'display:none', 'align-items:center', 'gap:.35rem',
    'transition:opacity .2s, transform .2s',
    'font-family:var(--font-body)'
  ].join(';');
  fab.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
  document.body.appendChild(fab);

  // Lógica de scroll
  let fabVisible = false;
  window.addEventListener('scroll', () => {
    const scrollY = window.scrollY;
    const threshold = 160; // px desde el top antes de mostrar el botón

    // Sombra en la info-bar cuando está pegada
    if (infoBar) {
      infoBar.classList.toggle('scrolled', scrollY > 20);
    }

    // Mostrar/ocultar botón flotante
    if (scrollY > threshold && !fabVisible) {
      fab.style.display = 'flex';
      requestAnimationFrame(() => { fab.style.opacity = '1'; fab.style.transform = 'translateY(0)'; });
      fabVisible = true;
    } else if (scrollY <= threshold && fabVisible) {
      fab.style.opacity = '0';
      fab.style.transform = 'translateY(6px)';
      setTimeout(() => { if (!fabVisible) fab.style.display = 'none'; }, 200);
      fabVisible = false;
    }
  }, { passive: true });
})();

/* 
   MODO HOJAS (Dinámico)
 */
async function cambiarModoPrep(modo) {
  const pId = _getPedidoId();
  if (!pId) return;
  try {
    const res = await fetch(`/api/pedido/${pId}/modo_preparacion`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modo })
    });
    const data = await res.json();
    if (data.ok) location.reload();
    else showToast(data.msg || 'Error al cambiar modo', 'error');
  } catch (e) {
    showToast('Error de red al intentar cambiar modo', 'error');
  }
}

function actualizarTarjetaHoja(uid, inicio, fin, persona) {
  const card = document.getElementById(`hoja-card-${uid}`);
  if (!card) return;

  card.classList.remove('tiene-inicio', 'tiene-todo');
  if (inicio && fin)   card.classList.add('tiene-todo');
  else if (inicio)     card.classList.add('tiene-inicio');

  const iniSpan = document.getElementById(`hoja-ini-${uid}`);
  const finSpan = document.getElementById(`hoja-fin-${uid}`);
  if (iniSpan) { iniSpan.textContent = ` ${fmtHora(inicio)}`; iniSpan.className = `sec-time ${inicio ? 'inicio' : 'empty'}`; }
  if (finSpan) { finSpan.textContent = `⏹ ${fmtHora(fin)}`;    finSpan.className = `sec-time ${fin ? 'fin' : 'empty'}`; }

  const badge = document.getElementById(`hoja-persona-badge-${uid}`);
  const txt   = document.getElementById(`hoja-persona-txt-${uid}`);
  if (badge && txt) {
    txt.textContent = persona || 'Sin asignar';
    badge.style.color      = persona ? '#1d4ed8' : 'var(--muted)';
    badge.style.background = persona ? '#eff6ff' : 'var(--surface2)';
  }

  const btnIni     = document.getElementById(`btn-hoja-ini-${uid}`);
  const btnFin     = document.getElementById(`btn-hoja-fin-${uid}`);
  const btnLimpiar = document.getElementById(`btn-hoja-limpiar-${uid}`);
  if (btnIni)     btnIni.style.display     = inicio ? 'none' : '';
  if (btnFin)     btnFin.style.display     = (inicio && !fin) ? '' : 'none';
  if (btnLimpiar) btnLimpiar.style.display = (inicio || fin) ? '' : 'none';

  const mIni = document.getElementById(`hoja-manual-ini-${uid}`);
  const mFin = document.getElementById(`hoja-manual-fin-${uid}`);
  if (mIni && inicio) mIni.value = inicio.substring(0,16).replace(' ','T');
  if (mFin && fin)    mFin.value = fin.substring(0,16).replace(' ','T');
}

async function _guardarHoja(pedido_id, hoja_num, tipo_campo, valor, persona, record_id) {
  try {
    let final_record_id = record_id;
    let isNew = (!record_id || record_id === 'None');

    if (isNew) {
      try {
        const resInit = await fetch(`/api/pedido/${pedido_id}/hoja/${hoja_num}/nueva`, { method: 'POST' });
        const dataInit = await resInit.json();
        if (dataInit.ok) final_record_id = dataInit.id;
        else { showToast('Error al inicializar registro de hoja', 'error'); return; }
      } catch (e) {
        showToast('Error de conexión', 'error');
        return;
      }
    }

    const res = await fetch(`/api/hoja_record/${final_record_id}`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ tipo_campo, valor, persona })
    });
    const data = await res.json();
    if (data.ok) {
      if (isNew) {
        const oldId = `new-${hoja_num}`;
        const newId = data.id;
        _patchHojaCardIds(oldId, newId, hoja_num);
        actualizarTarjetaHoja(newId, data.inicio, data.fin, data.persona);
        showToast(` Hoja inicializada y guardada.`, 'success');
      } else {
        actualizarTarjetaHoja(data.id, data.inicio, data.fin, data.persona);
        showToast(` Hoja Guardada.`, 'success');
      }
    } else {
      showToast(data.msg || 'No se pudo guardar la hoja', 'error');
    }
  } catch (e) {
    showToast('Error de red al guardar hoja', 'error');
  }
}

async function hojaAhora(pedido_id, hoja_num, tipo_campo, record_id) {
  const uid = record_id && record_id !== 'None' ? record_id : `new-${hoja_num}`;
  const persona = (document.getElementById(`hoja-persona-input-${uid}`) || {}).value || '';
  await _guardarHoja(pedido_id, hoja_num, tipo_campo, 'now', persona, record_id);
}

async function hojaManual(pedido_id, hoja_num, tipo_campo, record_id) {
  const uid = record_id && record_id !== 'None' ? record_id : `new-${hoja_num}`;
  const inputId = tipo_campo === 'inicio' ? `hoja-manual-ini-${uid}` : `hoja-manual-fin-${uid}`;
  const valor   = (document.getElementById(inputId) || {}).value || 'now';
  const persona = (document.getElementById(`hoja-persona-input-${uid}`) || {}).value || '';
  await _guardarHoja(pedido_id, hoja_num, tipo_campo, valor, persona, record_id);
}

async function actualizarPersonaHoja(uid, hoja_num) {
  const persona   = (document.getElementById(`hoja-persona-input-${uid}`) || {}).value || '';
  const iniSpan   = document.getElementById(`hoja-ini-${uid}`);
  const hayInicio = iniSpan && !iniSpan.textContent.includes('—');
  const pedido_id = _getPedidoId();
  const record_id = uid.startsWith('new-') ? null : uid;

  if (hayInicio) {
    const mIni  = document.getElementById(`hoja-manual-ini-${uid}`);
    const valor = mIni && mIni.value ? mIni.value : 'now';
    await _guardarHoja(pedido_id, hoja_num, 'inicio', valor, persona, record_id);
  } else {
    await _guardarHoja(pedido_id, hoja_num, null, null, persona, record_id);
  }
}

async function dividirHoja(pedido_id, hoja_num) {
  try {
    const res = await fetch(`/api/pedido/${pedido_id}/hoja/${hoja_num}/nueva`, { method: 'POST' });
    const data = await res.json();
    if (data.ok) location.reload();
  } catch(e) { showToast('Error al dividir hoja', 'error'); }
}

async function limpiarHoja(pedido_id, hoja_num, record_id) {
  if (!record_id || record_id === 'None') return;
  if (!confirm(`¿Limpiar o eliminar este fragmento de la hoja ${hoja_num}?`)) return;
  try {
    const res = await fetch(`/api/hoja_record/${record_id}/limpiar`, { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      if (data.deleted) location.reload();
      else {
        actualizarTarjetaHoja(record_id, null, null, null);
        const inp = document.getElementById(`hoja-persona-input-${record_id}`);
        if (inp) inp.value = '';
        showToast('↺ Hoja limpiada.', 'info');
      }
    } else showToast(data.msg || 'Error al limpiar', 'error');
  } catch (e) { showToast('Error de red', 'error'); }
}

/*  Helpers para parchar IDs dinámicamente (evita recarga de página)  */

/* 
   ACCIONES EN LOTE (Manejo de Checkboxes y Barra Flotante)
    */

function seleccionarTodasHojas(checked) {
  const checkboxes = document.querySelectorAll('.hoja-checkbox');
  checkboxes.forEach(cb => cb.checked = checked);
  actualizarBarraHojas();
}

function actualizarBarraHojas() {
  const checked = document.querySelectorAll('.hoja-checkbox:checked');
  const bar = document.getElementById('batch-hojas-bar');
  const countEl = document.getElementById('batch-hojas-count');
  
  if (checked.length > 0) {
    countEl.textContent = checked.length;
    bar.classList.add('visible');
    
    // Si la barra se vuelve visible y el input de hora está vacío, poner "ahora"
    const horaInput = document.getElementById('batch-hojas-hora');
    if (horaInput && !horaInput.value) {
      const ahora = new Date();
      const pad = n => String(n).padStart(2, '0');
      horaInput.value = `${ahora.getFullYear()}-${pad(ahora.getMonth()+1)}-${pad(ahora.getDate())}T${pad(ahora.getHours())}:${pad(ahora.getMinutes())}`;
    }

    // Sincronizar el nombre del banner superior si está lleno y el de la barra está vacío
    const bannerNombre = document.getElementById('operador-nombre').value;
    const batchNombre = document.getElementById('batch-hojas-persona');
    if (bannerNombre && batchNombre && !batchNombre.value) {
      batchNombre.value = bannerNombre;
    }
  } else {
    bar.classList.remove('visible');
    const allToggle = document.getElementById('check-all-hojas');
    if (allToggle) allToggle.checked = false;
  }
}

function seleccionarTodasSecciones(checked) {
  const checkboxes = document.querySelectorAll('.seccion-checkbox');
  checkboxes.forEach(cb => cb.checked = checked);
  actualizarBarraSecciones();
}

function actualizarBarraSecciones() {
  const checked = document.querySelectorAll('.seccion-checkbox:checked');
  const bar = document.getElementById('batch-secciones-bar');
  const countEl = document.getElementById('batch-secciones-count');
  
  if (checked.length > 0) {
    countEl.textContent = checked.length;
    bar.classList.add('visible');
    
    const horaInput = document.getElementById('batch-secciones-hora');
    if (horaInput && !horaInput.value) {
      const ahora = new Date();
      const pad = n => String(n).padStart(2, '0');
      horaInput.value = `${ahora.getFullYear()}-${pad(ahora.getMonth()+1)}-${pad(ahora.getDate())}T${pad(ahora.getHours())}:${pad(ahora.getMinutes())}`;
    }

    const bannerNombre = document.getElementById('operador-nombre').value;
    const batchNombre = document.getElementById('batch-secciones-persona');
    if (bannerNombre && batchNombre && !batchNombre.value) {
      batchNombre.value = bannerNombre;
    }
  } else {
    bar.classList.remove('visible');
    const allToggle = document.getElementById('check-all-secciones');
    if (allToggle) allToggle.checked = false;
  }
}

function limpiarSeleccionSecciones() {
  const checkboxes = document.querySelectorAll('.seccion-checkbox');
  checkboxes.forEach(cb => cb.checked = false);
  const allToggle = document.getElementById('check-all-secciones');
  if (allToggle) allToggle.checked = false;
  actualizarBarraSecciones();
}

function limpiarSeleccionHojas() {
  const checkboxes = document.querySelectorAll('.hoja-checkbox');
  checkboxes.forEach(cb => cb.checked = false);
  const allToggle = document.getElementById('check-all-hojas');
  if (allToggle) allToggle.checked = false;
  actualizarBarraHojas();
}

async function reclamarHojasMasivo() {
  const checked = document.querySelectorAll('.hoja-checkbox:checked');
  if (checked.length === 0) return;

  const nombre = document.getElementById('batch-hojas-persona').value.trim();
  const fechaManual = document.getElementById('batch-hojas-hora').value;
  
  if (!nombre) {
    showToast('Indica el nombre del responsable en la barra.', 'error');
    document.getElementById('batch-hojas-persona').focus();
    return;
  }

  if (!confirm(`¿Reclamar ${checked.length} hojas para ${nombre}?`)) return;

  const ids = Array.from(checked).map(cb => {
    const val = cb.value;
    return val.startsWith('new-') ? { hoja_num: cb.dataset.hoja } : { record_id: val };
  });

  const pedido_id = _getPedidoId();
  
  try {
    const res = await fetch(`/api/pedido/${pedido_id}/hoja/batch`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ 
        ids, 
        persona: nombre,
        valor: fechaManual,
        auto_inicio: true 
      })
    });
    
    const data = await res.json();
    if (data.ok) {
      showToast(` ${data.count} hojas reclamadas correctamente.`, 'success');
      limpiarSeleccionHojas();
      // En este caso, como son muchos, un reload es lo más seguro para ver todo actualizado
      // pero para mantener la fluidez prometida, intentaremos refrescar sin recargar si es posible.
      // Sin embargo, batch update es complejo de parchear 1 por 1.
      location.reload(); 
    } else {
      showToast(data.msg || 'Error al procesar lote', 'error');
    }
  } catch(e) {
    showToast('Error de red al procesar lote', 'error');
  }
}

async function reclamarSeccionesMasivo() {
  const checked = document.querySelectorAll('.seccion-checkbox:checked');
  if (checked.length === 0) return;

  const nombre = document.getElementById('batch-secciones-persona').value.trim();
  const fechaManual = document.getElementById('batch-secciones-hora').value;
  
  if (!nombre) {
    showToast('Indica el nombre del responsable en la barra.', 'error');
    document.getElementById('batch-secciones-persona').focus();
    return;
  }

  if (!confirm(`¿Reclamar ${checked.length} pasillos para ${nombre}?`)) return;

  const ids = Array.from(checked).map(cb => {
    const val = cb.value;
    return val.startsWith('new-') ? { sec_num: cb.dataset.sec } : { record_id: val };
  });

  const pedido_id = _getPedidoId();
  
  try {
    const res = await fetch(`/api/pedido/${pedido_id}/seccion/batch`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ 
        ids, 
        persona: nombre,
        valor: fechaManual,
        auto_inicio: true 
      })
    });
    
    const data = await res.json();
    if (data.ok) {
      showToast(` ${data.count} pasillos reclamados correctamente.`, 'success');
      limpiarSeleccionSecciones();
      location.reload(); 
    } else {
      showToast(data.msg || 'Error al procesar lote', 'error');
    }
  } catch(e) {
    showToast('Error de red al procesar lote', 'error');
  }
}

function _patchSectionCardIds(oldId, newId, sec_num) {
  const card = document.getElementById(`sec-card-${oldId}`);
  if (!card) return;
  card.id = `sec-card-${newId}`;
  card.setAttribute('data-record', newId);
  
  const idsToPatch = [
    ['sec-ini-', 'hoja-ini-'], // A veces se usa el mismo patrón
    ['sec-fin-', ''],
    ['sec-persona-badge-', ''],
    ['sec-persona-txt-', ''],
    ['sec-persona-input-', ''],
    ['btn-ini-', ''],
    ['btn-fin-', ''],
    ['btn-limpiar-', ''],
    ['sec-manual-', ''],
    ['sec-manual-ini-', ''],
    ['sec-manual-fin-', '']
  ];

  // Caso especial: Los elementos de pasillo usan prefijo 'sec-'
  _doPatch(oldId, newId, 'sec-');
}

function _patchHojaCardIds(oldId, newId, hoja_num) {
  const card = document.getElementById(`hoja-card-${oldId}`);
  if (!card) return;
  card.id = `hoja-card-${newId}`;
  
  _doPatch(oldId, newId, 'hoja-');
}

function _doPatch(oldId, newId, prefix) {
  const elements = document.querySelectorAll(`[id*="${oldId}"]`);
  elements.forEach(el => {
    if (el.id.includes(oldId)) {
      el.id = el.id.replace(oldId, newId);
    }
  });

  const buttons = document.querySelectorAll(`button[onclick*="'${oldId}'"]`);
  buttons.forEach(btn => {
    const oc = btn.getAttribute('onclick');
    btn.setAttribute('onclick', oc.replace(`'${oldId}'`, `'${newId}'`));
  });

  const inputs = document.querySelectorAll(`input[onchange*="'${oldId}'"]`);
  inputs.forEach(inp => {
    const oc = inp.getAttribute('onchange');
    inp.setAttribute('onchange', oc.replace(`'${oldId}'`, `'${newId}'`));
  });

  const checkboxes = document.querySelectorAll(`input[value="${oldId}"]`);
  checkboxes.forEach(cb => {
    cb.value = newId;
    cb.setAttribute('data-record', newId);
  });
}
