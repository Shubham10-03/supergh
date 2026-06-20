// Loader components — skeletons and spinners

export function tableLoader(rows = 5, cols = 4) {
  let html = '';
  for (let i = 0; i < rows; i++) {
    html += '<div class="skeleton-row">';
    for (let j = 0; j < cols; j++) {
      const width = 40 + Math.random() * 50;
      html += `<div class="skeleton-cell"><div class="skeleton" style="width:${width}%"></div></div>`;
    }
    html += '</div>';
  }
  return html;
}

export function pageLoader() {
  return `<div class="empty-state"><div class="skeleton" style="width:120px;height:20px;margin-bottom:12px"></div><div class="skeleton" style="width:200px;height:14px"></div></div>`;
}

export function inlineLoader() {
  return '<span class="skeleton" style="width:60px;height:12px;display:inline-block"></span>';
}
