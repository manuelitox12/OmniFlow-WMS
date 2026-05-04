/**
 * Agregar marcas, personas y personal sin recargar la página
 */

async function agregarMarca() {
  const input  = document.getElementById('nueva-marca');
  if (!input) return;
  const nombre = input.value.trim();
  if (!nombre) return;

  const res  = await fetch('/api/marcas', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ nombre })
  });
  const data = await res.json();

  if (data.ok) {
    location.reload();
  } else {
    alert('Error: ' + (data.msg || 'No se pudo agregar'));
  }
}

async function agregarPersona() {
  const input  = document.getElementById('nueva-persona');
  if (!input) return;
  const nombre = input.value.trim();
  if (!nombre) return;

  const res  = await fetch('/api/personas', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ nombre })
  });
  const data = await res.json();

  if (data.ok) {
    location.reload();
  } else {
    alert('Error: ' + (data.msg || 'No se pudo agregar'));
  }
}

async function agregarPersonal() {
  const nombre   = document.getElementById('personal-nombre').value.trim();
  const apellido = document.getElementById('personal-apellido').value.trim();
  const cedula   = document.getElementById('personal-cedula').value.trim();
  const area     = document.getElementById('personal-area').value;
  const alm_i    = document.getElementById('personal-alm-i').value;
  const alm_f    = document.getElementById('personal-alm-f').value;

  if (!nombre) {
    alert('El nombre del empleado es requerido.');
    document.getElementById('personal-nombre').focus();
    return;
  }

  const res  = await fetch('/api/personal', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ 
      nombre, 
      apellido, 
      cedula, 
      area, 
      almuerzo_inicio: alm_i, 
      almuerzo_fin: alm_f 
    })
  });
  const data = await res.json();

  if (data.ok) {
    location.reload();
  } else {
    alert('Error: ' + (data.msg || 'No se pudo agregar'));
  }
}

const mt = document.getElementById('nueva-marca');
if(mt) mt.addEventListener('keydown', e => {
  if (e.key === 'Enter') agregarMarca();
});

const mp = document.getElementById('nueva-persona');
if(mp) mp.addEventListener('keydown', e => {
  if (e.key === 'Enter') agregarPersona();
});

const pc = document.getElementById('personal-cedula');
if(pc) pc.addEventListener('keydown', e => {
  if (e.key === 'Enter') agregarPersonal();
});

function toggleEdit(id) {
  const rowView = document.getElementById(`row-view-${id}`);
  const rowEdit = document.getElementById(`row-edit-${id}`);
  if (rowView && rowEdit) {
    const isEditing = rowEdit.style.display !== 'none';
    rowEdit.style.display = isEditing ? 'none' : 'table-row';
    rowView.style.display = isEditing ? 'table-row' : 'none';
  }
}

async function savePersonal(id) {
  const nombre   = document.getElementById(`edit-nombre-${id}`).value.trim();
  const apellido = document.getElementById(`edit-apellido-${id}`).value.trim();
  const cedula   = document.getElementById(`edit-cedula-${id}`).value.trim();
  const area     = document.getElementById(`edit-area-${id}`).value;
  const alm_i    = document.getElementById(`edit-alm-i-${id}`).value;
  const alm_f    = document.getElementById(`edit-alm-f-${id}`).value;

  if (!nombre) {
    alert('El nombre es obligatorio.');
    return;
  }

  // Usamos un form real para que el redirect de Flask funcione normalmente
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = `/editar_personal/${id}`;

  const fields = { 
    nombre, 
    apellido, 
    cedula, 
    area, 
    almuerzo_inicio: alm_i, 
    almuerzo_fin: alm_f 
  };
  for (const [key, val] of Object.entries(fields)) {
    const input = document.createElement('input');
    input.type  = 'hidden';
    input.name  = key;
    input.value = val;
    form.appendChild(input);
  }

  document.body.appendChild(form);
  form.submit();
}
