const PALETTE = [];
const app = document.querySelector('#app');
const manifestPath = app.dataset.manifest;
const nav = document.querySelector('#editor-nav');
const status = document.querySelector('#storage-status');
const homeTemplate = document.querySelector('#home-template');
const state = { manifest: null, files: new Map(), localRoot: null, activePath: null, activeEditor: null, selectedGlyph: 0, selectedColor: 1, selectedSelector: 1 };

const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();
const $ = (selector, root = document) => root.querySelector(selector);
const el = (tag, attributes = {}, children = []) => {
  const node = document.createElement(tag);
  Object.entries(attributes).forEach(([key, value]) => key === 'class' ? node.className = value : key.startsWith('on') ? node.addEventListener(key.slice(2), value) : node.setAttribute(key, value));
  children.flat().forEach(child => node.append(child instanceof Node ? child : document.createTextNode(child)));
  return node;
};

async function inflate(bytes) {
  return new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate'))).arrayBuffer());
}
async function deflate(bytes) {
  return new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream('deflate'))).arrayBuffer());
}
function crc32(bytes) {
  let crc = -1;
  for (const value of bytes) {
    crc ^= value;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  return (crc ^ -1) >>> 0;
}
function chunk(type, payload) {
  const header = new Uint8Array(8 + payload.length + 4);
  const view = new DataView(header.buffer);
  view.setUint32(0, payload.length);
  header.set(textEncoder.encode(type), 4);
  header.set(payload, 8);
  view.setUint32(8 + payload.length, crc32(header.slice(4, 8 + payload.length)));
  return header;
}
function concat(parts) { const length = parts.reduce((sum, part) => sum + part.length, 0); const output = new Uint8Array(length); let offset = 0; for (const part of parts) { output.set(part, offset); offset += part.length; } return output; }
async function decodeIndexedPng(buffer) {
  const data = new Uint8Array(buffer); const signature = '\x89PNG\r\n\x1a\n';
  if (textDecoder.decode(data.slice(0, 8)) !== signature) throw new Error('Expected PNG file');
  let width, height, palette, compressed = []; let offset = 8;
  while (offset < data.length) {
    const length = new DataView(data.buffer, data.byteOffset + offset).getUint32(0); const type = textDecoder.decode(data.slice(offset + 4, offset + 8)); const body = data.slice(offset + 8, offset + 8 + length); offset += length + 12;
    if (type === 'IHDR') { const view = new DataView(body.buffer, body.byteOffset); width = view.getUint32(0); height = view.getUint32(4); if (body[8] !== 8 || body[9] !== 3 || body[12] !== 0) throw new Error('Expected non-interlaced indexed 8-bit PNG'); }
    if (type === 'PLTE') palette = Array.from({ length: body.length / 3 }, (_, index) => `#${[body[index * 3], body[index * 3 + 1], body[index * 3 + 2]].map(value => value.toString(16).padStart(2, '0')).join('')}`);
    if (type === 'IDAT') compressed.push(body);
    if (type === 'IEND') break;
  }
  const raw = await inflate(concat(compressed)); const pixels = new Uint8Array(width * height); let previous = new Uint8Array(width); offset = 0;
  for (let y = 0; y < height; y++) {
    const filter = raw[offset++], encoded = raw.slice(offset, offset += width), row = new Uint8Array(width);
    for (let x = 0; x < width; x++) {
      const left = x ? row[x - 1] : 0, above = previous[x], upperLeft = x ? previous[x - 1] : 0;
      if (filter === 0) row[x] = encoded[x];
      else if (filter === 1) row[x] = (encoded[x] + left) & 255;
      else if (filter === 2) row[x] = (encoded[x] + above) & 255;
      else if (filter === 3) row[x] = (encoded[x] + Math.floor((left + above) / 2)) & 255;
      else if (filter === 4) { const p = left + above - upperLeft, pa = Math.abs(p - left), pb = Math.abs(p - above), pc = Math.abs(p - upperLeft); row[x] = (encoded[x] + (pa <= pb && pa <= pc ? left : pb <= pc ? above : upperLeft)) & 255; }
      else throw new Error('Unsupported PNG filter');
    }
    pixels.set(row, y * width); previous = row;
  }
  return { type: 'png', width, height, palette, pixels, dirty: false };
}
async function encodeIndexedPng(image) {
  const rows = new Uint8Array((image.width + 1) * image.height);
  for (let y = 0; y < image.height; y++) rows.set(image.pixels.slice(y * image.width, (y + 1) * image.width), y * (image.width + 1) + 1);
  const palette = new Uint8Array(image.palette.flatMap(color => [parseInt(color.slice(1, 3), 16), parseInt(color.slice(3, 5), 16), parseInt(color.slice(5, 7), 16)]));
  const header = new Uint8Array(13); const view = new DataView(header.buffer); view.setUint32(0, image.width); view.setUint32(4, image.height); header.set([8, 3, 0, 0, 0], 8);
  return concat([new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', header), chunk('PLTE', palette), chunk('IDAT', await deflate(rows)), chunk('IEND', new Uint8Array())]);
}
async function directoryFile(path, create = false) {
  const bits = path.split('/'); let folder = state.localRoot;
  for (const part of bits.slice(0, -1)) folder = await folder.getDirectoryHandle(part, { create });
  return folder.getFileHandle(bits.at(-1), { create });
}
async function readPath(path) {
  if (state.files.has(path)) return state.files.get(path);
  let buffer;
  if (state.localRoot) buffer = await (await directoryFile(path)).getFile().then(file => file.arrayBuffer());
  else { const response = await fetch(path); if (!response.ok) throw new Error(`Could not load ${path}`); buffer = await response.arrayBuffer(); }
  const file = path.endsWith('.png') ? await decodeIndexedPng(buffer) : path.endsWith('.json') ? { type: 'json', value: JSON.parse(textDecoder.decode(buffer)), dirty: false } : { type: 'text', value: textDecoder.decode(buffer), dirty: false };
  state.files.set(path, file); return file;
}
async function writePath(path) {
  const file = state.files.get(path); if (!file) return;
  const bytes = file.type === 'png' ? await encodeIndexedPng(file) : textEncoder.encode(file.type === 'json' ? `${JSON.stringify(file.value, null, 2)}\n` : file.value);
  if (state.localRoot) { const writable = await (await directoryFile(path, true)).createWritable(); await writable.write(bytes); await writable.close(); file.dirty = false; status.textContent = `Saved ${path}`; }
  else { const link = el('a', { href: URL.createObjectURL(new Blob([bytes], { type: file.type === 'png' ? 'image/png' : 'text/plain' })), download: path.split('/').at(-1) }); link.click(); URL.revokeObjectURL(link.href); status.textContent = `Downloaded ${path}`; }
}
function markDirty(path) { const file = state.files.get(path); if (file) file.dirty = true; state.activePath = path; }
function paletteControls(selected, onChange) {
  const wrap = el('div', { class: 'palette', 'aria-label': 'C64 palette' });
  PALETTE.forEach((color, index) => wrap.append(el('button', { type: 'button', class: `swatch ${index === selected ? 'active' : ''}`, title: `${index}: ${color}`, style: `background:${color}`, onclick: () => onChange(index) })));
  return wrap;
}
function canvasContext(canvas, width, height) { canvas.width = width; canvas.height = height; return canvas.getContext('2d', { alpha: false }); }
function glyphByte(map, cell) { return map.pixels[cell * 2] * 16 + map.pixels[cell * 2 + 1]; }
function setGlyphByte(map, cell, value) { map.pixels[cell * 2] = value >> 4; map.pixels[cell * 2 + 1] = value & 15; }
function glyphPixels(atlas, glyph) { const pixels = []; const originX = (glyph % 16) * 8, originY = Math.floor(glyph / 16) * 8; for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) pixels.push(atlas.pixels[(originY + y) * atlas.width + originX + x]); return pixels; }
function drawGlyph(ctx, atlas, glyph, x, y, ink, scale = 1) { const pixels = glyphPixels(atlas, glyph); ctx.fillStyle = PALETTE[ink]; for (let py = 0; py < 8; py++) for (let px = 0; px < 8; px++) if (pixels[py * 8 + px]) ctx.fillRect(x + px * scale, y + py * scale, scale, scale); }
function titleStateMap(base, selection, selected) { const clone = { ...base, pixels: new Uint8Array(base.pixels) }; if (!selection || selected === 'one') return clone; for (const [offset, value] of selection.states[selected].screen) setGlyphByte(clone, offset, value); return clone; }
function titleStateColor(base, selection, selected) { const clone = { ...base, pixels: new Uint8Array(base.pixels) }; if (!selection || selected === 'one') return clone; for (const [offset, value] of selection.states[selected].color) clone.pixels[offset] = value; return clone; }
function drawCharacterScreen(canvas, atlas, glyphMap, colorMap, scale = 1) { const ctx = canvasContext(canvas, 320 * scale, 200 * scale); ctx.fillStyle = PALETTE[0]; ctx.fillRect(0, 0, canvas.width, canvas.height); for (let cell = 0; cell < 1000; cell++) drawGlyph(ctx, atlas, glyphByte(glyphMap, cell), (cell % 40) * 8 * scale, Math.floor(cell / 40) * 8 * scale, colorMap.pixels[cell], scale); }
function drawBitmap(canvas, selectors, high, low, ram, scale = 1, overlay = null) { const ctx = canvasContext(canvas, 320 * scale, 200 * scale); for (let y = 0; y < 200; y++) for (let x = 0; x < 160; x++) { const cell = Math.floor(y / 8) * 40 + Math.floor(x / 4), slot = selectors.pixels[y * 160 + x], colors = [0, high.pixels[cell], low.pixels[cell], ram.pixels[cell]]; ctx.fillStyle = PALETTE[colors[slot]]; ctx.fillRect(x * 2 * scale, y * scale, 2 * scale, scale); }
  if (overlay) { ctx.strokeStyle = PALETTE[7]; ctx.lineWidth = scale; overlay.forEach(([x, y, w, h, label]) => { ctx.strokeRect(x * 2 * scale, y * scale, w * 2 * scale, h * scale); ctx.fillStyle = PALETTE[1]; ctx.fillText(label, x * 2 * scale + 2, y * scale + 10); }); }
}
function clientPoint(event, canvas, width, height) { const rect = canvas.getBoundingClientRect(); return [Math.max(0, Math.min(width - 1, Math.floor((event.clientX - rect.left) * width / rect.width))), Math.max(0, Math.min(height - 1, Math.floor((event.clientY - rect.top) * height / rect.height)))]; }
function renderNav() { nav.replaceChildren(...[...state.manifest.editors].map(editor => el('a', { href: `#${editor.id}`, class: location.hash.slice(1) === editor.id ? 'active' : '' }, [editor.label]))); }
function editorShell(editor, inspector, content) { const root = el('section', { class: 'editor' }); root.append(el('aside', { class: 'inspector' }, [el('h1', {}, [editor.label]), inspector]), el('section', { class: 'canvas-panel' }, content)); app.replaceChildren(root); app.focus(); }
function selectControl(label, values, value, onChange) { return el('label', {}, [label, el('select', { onchange: event => onChange(event.target.value) }, values.map(([id, name]) => el('option', { value: id, ...(id === value ? { selected: '' } : {}) }, [name])))]); }

async function renderGlyphEditor(editor) {
  const charset = state.manifest.charsets.find(item => item.id === editor.charset), atlas = await readPath(charset.path); state.activePath = charset.path;
  const allScreens = state.manifest.editors.filter(item => item.kind === 'petscii-screen'); const maps = await Promise.all(allScreens.map(item => readPath(item.glyph_map)));
  const usages = Array.from({ length: 256 }, () => 0); maps.forEach(map => { for (let cell = 0; cell < 1000; cell++) usages[glyphByte(map, cell)]++; });
  const atlasCanvas = el('canvas'), detailCanvas = el('canvas'), count = el('p', { class: 'counter' });
  const draw = () => {
    const ctx = canvasContext(atlasCanvas, 512, 512); ctx.fillStyle = PALETTE[0]; ctx.fillRect(0, 0, 512, 512); for (let glyph = 0; glyph < 256; glyph++) { drawGlyph(ctx, atlas, glyph, (glyph % 16) * 32, Math.floor(glyph / 16) * 32, 1, 4); if (glyph === state.selectedGlyph) { ctx.strokeStyle = PALETTE[7]; ctx.lineWidth = 2; ctx.strokeRect((glyph % 16) * 32, Math.floor(glyph / 16) * 32, 32, 32); } }
    const dctx = canvasContext(detailCanvas, 256, 256); dctx.fillStyle = PALETTE[0]; dctx.fillRect(0, 0, 256, 256); drawGlyph(dctx, atlas, state.selectedGlyph, 0, 0, 1, 32); dctx.strokeStyle = '#444'; for (let n = 0; n <= 8; n++) { dctx.beginPath(); dctx.moveTo(n * 32, 0); dctx.lineTo(n * 32, 256); dctx.moveTo(0, n * 32); dctx.lineTo(256, n * 32); dctx.stroke(); }
    count.textContent = `Glyph ${state.selectedGlyph} is used ${usages[state.selectedGlyph]} times across title and INFO glyph maps.`;
  };
  atlasCanvas.addEventListener('click', event => { const [x, y] = clientPoint(event, atlasCanvas, 512, 512); state.selectedGlyph = Math.floor(y / 32) * 16 + Math.floor(x / 32); draw(); });
  detailCanvas.addEventListener('click', event => { const [x, y] = clientPoint(event, detailCanvas, 256, 256); const ax = (state.selectedGlyph % 16) * 8 + Math.floor(x / 32), ay = Math.floor(state.selectedGlyph / 16) * 8 + Math.floor(y / 32); atlas.pixels[ay * atlas.width + ax] ^= 1; markDirty(charset.path); draw(); });
  const picker = el('input', { type: 'number', min: '0', max: '255', value: state.selectedGlyph, onchange: event => { state.selectedGlyph = Math.max(0, Math.min(255, Number(event.target.value))); draw(); } });
  editorShell(editor, [el('p', { class: 'help' }, ['Select a glyph in the 16×16 atlas, then click its 8×8 editor to toggle pixels. Every PETSCII screen using this charset updates immediately.']), el('h2', {}, ['Glyph']), picker, count], [el('div', { class: 'glyph-layout' }, [atlasCanvas, el('div', { class: 'glyph-detail' }, [detailCanvas, el('p', { class: 'legend' }, ['White is set; black is clear. The save control writes atlas.png to a selected local project or downloads it.'])])])]); draw();
}
async function renderPetsciiEditor(editor) {
  const atlas = await readPath(state.manifest.charsets.find(item => item.id === editor.charset).path), baseMap = await readPath(editor.glyph_map), baseColor = await readPath(editor.color_map); let selectedState = 'one'; const selection = editor.selection ? (await readPath(editor.selection)).value : null; const canvas = el('canvas'); const glyphInput = el('input', { type: 'number', min: '0', max: '255', value: '0' }); const selected = el('p', { class: 'counter' });
  const maps = () => editor.id === 'title' ? [titleStateMap(baseMap, selection, selectedState), titleStateColor(baseColor, selection, selectedState)] : [baseMap, baseColor];
  const redraw = () => { const [map, color] = maps(); drawCharacterScreen(canvas, atlas, map, color); };
  canvas.addEventListener('click', event => { const [x, y] = clientPoint(event, canvas, 320, 200); const cell = Math.floor(y / 8) * 40 + Math.floor(x / 8); const [map, color] = maps(); selected.textContent = `Cell ${cell} · row ${Math.floor(cell / 40)}, column ${cell % 40} · glyph ${glyphByte(map, cell)} · color ${color.pixels[cell]}`; if (event.shiftKey) { baseColor.pixels[cell] = state.selectedColor; markDirty(editor.color_map); } else { setGlyphByte(baseMap, cell, Math.max(0, Math.min(255, Number(glyphInput.value)))); markDirty(editor.glyph_map); } redraw(); });
  const inspector = [el('p', { class: 'help' }, ['Click an 8×8 cell to set the selected glyph. Shift-click a cell to set its color. Title selection previews apply the small delta table but edits stay in the single title base map.']), glyphInput, el('h2', {}, ['Cell color']), paletteControls(state.selectedColor, value => { state.selectedColor = value; redraw(); }), selected];
  if (selection) inspector.splice(1, 0, selectControl('Preview selection', [['one', 'One Player'], ['two', 'Two Player'], ['auto', 'AI vs AI']], selectedState, value => { selectedState = value; redraw(); }));
  editorShell(editor, inspector, [el('div', { class: 'canvas-toolbar' }, [el('strong', {}, ['40 × 25 character screen']), el('span', { class: 'legend' }, ['Click: glyph · Shift-click: color'])]), canvas]); redraw();
}
async function renderBitmapEditor(editor) {
  const [selectors, high, low, ram, layout] = await Promise.all([readPath(editor.selectors), readPath(editor.screen_high), readPath(editor.screen_low), readPath(editor.color_ram), readPath(editor.layout)]); const canvas = el('canvas'); let mode = 'selector', slot = 1; const readLayout = () => Object.entries(layout.value.cell_rectangles).map(([id, data]) => [...data.logical_xywh, id.toUpperCase()]);
  const redraw = () => drawBitmap(canvas, selectors, high, low, ram, 2, readLayout());
  canvas.addEventListener('click', event => { const [physicalX, y] = clientPoint(event, canvas, 640, 400); const x = Math.floor(physicalX / 4), cell = Math.floor(y / 8) * 40 + Math.floor(x / 4); if (mode === 'selector') { selectors.pixels[y * 160 + x] = state.selectedSelector; markDirty(editor.selectors); } else { const target = [null, high, low, ram][slot]; target.pixels[cell] = state.selectedColor; markDirty([null, editor.screen_high, editor.screen_low, editor.color_ram][slot]); } redraw(); });
  const inspector = [el('p', { class: 'help' }, ['The bitmap is 160×200 logical pixels. Each displayed pixel is 2×1 physical pixels. In selector mode click to assign 00/01/10/11. In local-color mode click any pixel in a 4×8 cell to set the chosen local color slot.']), selectControl('Edit mode', [['selector', '2-bit selector'], ['color', 'Local cell color']], mode, value => { mode = value; redraw(); }), selectControl('Selector / local slot', [['0', '00 background'], ['1', '01 screen high'], ['2', '10 screen low'], ['3', '11 Color RAM']], String(slot), value => { slot = Number(value); state.selectedSelector = slot; redraw(); }), el('h2', {}, ['Color']), paletteControls(state.selectedColor, value => { state.selectedColor = value; redraw(); })];
  editorShell(editor, inspector, [el('div', { class: 'canvas-toolbar' }, [el('strong', {}, ['160 × 200 logical-pixel board']), el('span', { class: 'legend' }, ['Outlined A–I rectangles come from game/board/layout.json'])]), canvas]); redraw();
}
async function renderMarksEditor(editor) {
  const markPicker = el('select'); editor.marks.forEach(mark => markPicker.append(el('option', { value: mark.id }, [mark.id.toUpperCase()]))); let current = editor.marks[0]; const canvas = el('canvas'); const preview = el('p', { class: 'mark-preview' });
  const redraw = async () => { const image = await readPath(current.path); const ctx = canvasContext(canvas, image.width * 32, image.height * 32); for (let y = 0; y < image.height; y++) for (let x = 0; x < image.width; x++) { ctx.fillStyle = PALETTE[image.pixels[y * image.width + x]]; ctx.fillRect(x * 32, y * 32, 32, 32); ctx.strokeStyle = '#333'; ctx.strokeRect(x * 32, y * 32, 32, 32); } preview.textContent = `${current.id.toUpperCase()} is ${image.width}×${image.height} logical multicolor pixels. Click a cell to assign the selected C64 color.`; state.activePath = current.path; };
  canvas.addEventListener('click', async event => { const image = await readPath(current.path); const [x, y] = clientPoint(event, canvas, canvas.width, canvas.height); image.pixels[Math.floor(y / 32) * image.width + Math.floor(x / 32)] = state.selectedColor; markDirty(current.path); redraw(); });
  markPicker.addEventListener('change', async event => { current = editor.marks.find(mark => mark.id === event.target.value); await redraw(); });
  editorShell(editor, [el('p', { class: 'help' }, ['Marks use palette indexes directly. Black is transparent against the board; the other colors can use the board cell’s available local slots.']), el('label', {}, ['Mark', markPicker]), el('h2', {}, ['Paint color']), paletteControls(state.selectedColor, value => { state.selectedColor = value; redraw(); })], [el('div', { class: 'mark-layout' }, [canvas, preview])]); await redraw();
}
function markdownLines(markdown, width) { return markdown.split('\n').flatMap(line => { const clean = line.replace(/^#{1,6}\s*/, '').replace(/^[-*]\s+/, '• ').replace(/^>\s*/, '').replace(/\*\*(.*?)\*\*/g, '$1').replace(/\*(.*?)\*/g, '$1').replace(/\|/g, ' ').replace(/`/g, ''); const words = clean.trim().split(/\s+/).filter(Boolean); const rows = []; let row = ''; words.forEach(word => { if (`${row} ${word}`.trim().length > width) { rows.push(row); row = word; } else row = `${row} ${word}`.trim(); }); if (row) rows.push(row); return rows.length ? rows : ['']; }); }
async function renderMarkdownEditor(editor) {
  const [archive, atlas, glyphMap, colorMap] = await Promise.all([readPath(editor.path), readPath(state.manifest.charsets.find(item => item.id === editor.charset).path), readPath('assets/info/glyph-map.png'), readPath('assets/info/color-map.png')]); const textarea = el('textarea', {}, [archive.value]); const scroll = el('input', { type: 'number', min: '0', value: '0' }); const canvas = el('canvas');
  const code = character => { const char = character.toUpperCase(); if (char >= 'A' && char <= 'Z') return char.charCodeAt(0) - 64; if (char >= '0' && char <= '9') return char.charCodeAt(0) - 21; return { ' ': 0, '?': 37, ':': 38, '.': 39, ',': 40, '/': 41, '-': 42, '!': 43, '(': 45, ')': 46, '"': 47, '|': 55 }.at(char) ?? 0; };
  const redraw = () => { drawCharacterScreen(canvas, atlas, glyphMap, colorMap, 2); const ctx = canvas.getContext('2d'); const rows = markdownLines(textarea.value, editor.viewport[0]); const start = Math.min(Number(scroll.value), Math.max(0, rows.length - editor.viewport[1])); for (let y = 0; y < editor.viewport[1]; y++) { const text = rows[start + y] ?? ''; for (let x = 0; x < editor.viewport[0]; x++) { ctx.fillStyle = PALETTE[0]; ctx.fillRect((5 + x) * 16, (4 + y) * 16, 16, 16); drawGlyph(ctx, atlas, code(text[x] ?? ' '), (5 + x) * 16, (4 + y) * 16, 1, 2); } } scroll.max = Math.max(0, rows.length - editor.viewport[1]); };
  textarea.addEventListener('input', () => { archive.value = textarea.value; markDirty(editor.path); redraw(); }); scroll.addEventListener('input', redraw);
  editorShell(editor, [el('p', { class: 'help' }, ['This is a browser preview of the 29×18 INFO viewport. It mirrors the project’s basic heading, list, quote, and table text treatment; run scripts/compile_info_markdown.py for the final C64 payload.']), el('label', {}, ['Scroll row', scroll]), el('p', { class: 'notice' }, ['The static site cannot commit to GitHub. Open a local project to write archive.md, or download the changed file.'])], [el('div', { class: 'markdown-layout' }, [textarea, canvas])]); redraw(); state.activePath = editor.path;
}
async function renderLayoutEditor(editor) {
  const boardPath = editor.paths.find(path => path.endsWith('layout.json')); const board = await readPath(boardPath), manifestFile = { type: 'json', value: state.manifest, dirty: false }; const picker = el('select'); [['board', 'Board mark rectangles'], ['info', 'INFO text viewport'], ['title', 'Title selection rows']].forEach(([id, label]) => picker.append(el('option', { value: id }, [label]))); const textarea = el('textarea'); const canvas = el('canvas'); let kind = 'board';
  const source = () => kind === 'board' ? board : manifestFile;
  const jsonForKind = () => kind === 'board' ? board.value : kind === 'info' ? state.manifest.layouts['info-text'] : state.manifest.layouts['title-selection'];
  const setJson = value => { if (kind === 'board') board.value = value; else if (kind === 'info') state.manifest.layouts['info-text'] = value; else state.manifest.layouts['title-selection'] = value; state.files.set(manifestPath, manifestFile); markDirty(kind === 'board' ? boardPath : manifestPath); };
  const redraw = async () => { textarea.value = JSON.stringify(jsonForKind(), null, 2); const ctx = canvasContext(canvas, 640, 400); ctx.fillStyle = PALETTE[0]; ctx.fillRect(0, 0, 640, 400); if (kind === 'board') { const e = state.manifest.editors.find(item => item.id === 'board'); const [selectors, high, low, ram] = await Promise.all([readPath(e.selectors), readPath(e.screen_high), readPath(e.screen_low), readPath(e.color_ram)]); drawBitmap(canvas, selectors, high, low, ram, 2, Object.entries(board.value.cell_rectangles).map(([id, data]) => [...data.logical_xywh, id.toUpperCase()])); } else { ctx.fillStyle = PALETTE[4]; ctx.fillRect(0, 0, 640, 400); ctx.strokeStyle = PALETTE[7]; ctx.lineWidth = 2; const layout = jsonForKind(); if (kind === 'info') ctx.strokeRect(layout.x * 16, layout.y * 16, layout.width * 16, layout.height * 16); else layout.rows.forEach(row => ctx.strokeRect(layout.text_x * 16, row * 16, 20 * 16, 16)); } };
  picker.addEventListener('change', async event => { kind = event.target.value; await redraw(); }); textarea.addEventListener('change', async () => { try { setJson(JSON.parse(textarea.value)); await redraw(); } catch (error) { alert(`Invalid JSON: ${error.message}`); } });
  editorShell(editor, [el('p', { class: 'help' }, ['Edit actual layout JSON. Board changes update the named A–I mark rectangles. INFO and title changes are saved in asset-studio.json and act as editor configuration for their overlays.']), el('label', {}, ['Layout', picker]), el('p', { class: 'notice' }, ['Use Download active file or Open local project to retain changes.'])], [el('div', { class: 'layout-layout' }, [textarea, canvas])]); await redraw();
}
async function renderHome() { const fragment = homeTemplate.content.cloneNode(true); const cards = fragment.querySelector('#home-cards'); state.manifest.editors.forEach(editor => cards.append(el('a', { href: `#${editor.id}` }, [el('strong', {}, [editor.label]), el('small', {}, [({ 'glyph-atlas': 'Edit reusable 8×8 glyphs and see shared usage.', 'petscii-screen': 'Edit 40×25 glyph and color maps.', 'multicolor-bitmap': 'Edit 2-bit bitmap selectors and local colors.', mark: 'Paint logical X and O mark pixels.', markdown: 'Edit archive Markdown with an INFO viewport preview.', layout: 'Move text, selections, and mark rectangles.' })[editor.kind]])]))); app.replaceChildren(fragment); }
async function route() { try { const id = location.hash.slice(1); renderNav(); if (!id) return renderHome(); const editor = state.manifest.editors.find(item => item.id === id); if (!editor) return renderHome(); state.activeEditor = editor; if (editor.kind === 'glyph-atlas') await renderGlyphEditor(editor); if (editor.kind === 'petscii-screen') await renderPetsciiEditor(editor); if (editor.kind === 'multicolor-bitmap') await renderBitmapEditor(editor); if (editor.kind === 'mark') await renderMarksEditor(editor); if (editor.kind === 'markdown') await renderMarkdownEditor(editor); if (editor.kind === 'layout') await renderLayoutEditor(editor); } catch (error) { app.replaceChildren(el('section', { class: 'notice' }, [`Editor error: ${error.message}`])); console.error(error); } }
async function openLocal() { if (!window.showDirectoryPicker) { alert('This browser does not support the File System Access API. Use Download active file instead.'); return; } try { state.localRoot = await window.showDirectoryPicker({ mode: 'readwrite' }); state.files.clear(); state.manifest = (await readPath(manifestPath)).value; status.textContent = `Local project: ${state.localRoot.name}`; await route(); } catch (error) { if (error.name !== 'AbortError') alert(error.message); } }
async function saveActive() { if (!state.activePath) return; await writePath(state.activePath); }
async function boot() { state.manifest = (await readPath(manifestPath)).value; PALETTE.push(...state.manifest.palette.colors); renderNav(); await route(); }
window.addEventListener('hashchange', route); $('#open-local').addEventListener('click', openLocal); $('#download-active').addEventListener('click', saveActive); boot();
