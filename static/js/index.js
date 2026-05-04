/*  Reloj de fecha  */
function actualizarFecha() {
  const ahora = new Date();
  const fechaInput = document.getElementById('fecha');
  if (fechaInput) {
    fechaInput.value = ahora.toLocaleString('es-PA', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false
    });
  }
}
actualizarFecha();
setInterval(actualizarFecha, 60000);

/*  Banner informativo según tipo seleccionado  */
function actualizarBanner() {
  const elEmpaque = document.getElementById('tipo-empaque');
  if (!elEmpaque) return;
  
  const esEmpaque = elEmpaque.checked;
  const banner    = document.getElementById('tipo-banner');

  if (esEmpaque) {
    banner.className = 'tipo-info-banner tipo-info-empaque';
    banner.innerHTML = ' Flujo: <strong>pendiente → empacando → empacado → retirado</strong>';
  } else {
    banner.className = 'tipo-info-banner tipo-info-directo';
    banner.innerHTML = ' Flujo: <strong>pendiente → retirado</strong> (sin paso de empaque)';
  }
}

/*  Prevenir doble submit  */
const formPedido = document.getElementById('form-pedido');
if (formPedido) {
  formPedido.addEventListener('submit', function() {
    const btn      = document.getElementById('btn-submit');
    btn.textContent = '⏳ Guardando...';
    btn.disabled    = true;
  });
}
