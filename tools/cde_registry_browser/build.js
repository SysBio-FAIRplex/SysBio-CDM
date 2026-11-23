// Assembles the single-file browser: node build.js  →  cde_registry_browser.html (next to this script)
const fs = require('fs'), path = require('path');
const src = p => fs.readFileSync(path.join(__dirname, 'src', p), 'utf8');
const parts = ['ui_base.js', 'ui_sheet.js', 'ui_l2.js', 'ui_clusters.js', 'ui_main.js'];
const app = parts.map(p => '/* ==== ' + p + ' ==== */\n' + src(p)).join('\n');
const core = src('core.js'), css = src('style.css');
for (const [n, t] of [['core', core], ['app', app]]) if (/<\/script/i.test(t)) throw new Error(n + ' contains </script');
let html = src('shell.html');
for (const [k, v] of [['%%CSS%%', css], ['%%CORE%%', core], ['%%APP%%', app]]) { if (html.split(k).length !== 2) throw new Error('placeholder ' + k); html = html.split(k).join(v); }
fs.writeFileSync(path.join(__dirname, 'cde_registry_browser.html'), html);
console.log('cde_registry_browser.html', html.length, 'bytes');
