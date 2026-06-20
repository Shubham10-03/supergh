// Modal component — generic overlay

let activeModal = null;

export function openModal(title, contentHtml, actions = []) {
  closeModal();
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-title">${title}</div>
      <div class="modal-content">${contentHtml}</div>
      <div class="modal-actions" id="modal-actions"></div>
    </div>
  `;

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  document.addEventListener('keydown', handleEsc);
  document.body.appendChild(overlay);
  requestAnimationFrame(() => overlay.classList.add('open'));

  const actionsEl = overlay.querySelector('#modal-actions');
  actions.forEach(({ label, cls, onClick }) => {
    const btn = document.createElement('button');
    btn.className = `btn ${cls || 'btn-ghost'}`;
    btn.textContent = label;
    btn.onclick = () => onClick(overlay);
    actionsEl.appendChild(btn);
  });

  activeModal = overlay;
  return overlay;
}

export function closeModal() {
  if (activeModal) {
    activeModal.classList.remove('open');
    setTimeout(() => activeModal?.remove(), 150);
    activeModal = null;
  }
  document.removeEventListener('keydown', handleEsc);
}

function handleEsc(e) {
  if (e.key === 'Escape') closeModal();
}

export function confirmDialog(message, { title = 'Confirm', confirmLabel = 'Confirm', danger = false } = {}) {
  return new Promise((resolve) => {
    openModal(title, `<div class="confirm-body">${message}</div>`, [
      { label: 'Cancel', cls: 'btn-ghost', onClick: () => { closeModal(); resolve(false); } },
      { label: confirmLabel, cls: danger ? 'btn-danger' : 'btn-primary', onClick: () => { closeModal(); resolve(true); } },
    ]);
  });
}
