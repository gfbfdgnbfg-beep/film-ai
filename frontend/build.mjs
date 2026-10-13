// V0.5 uses a dependency-free static Hybrid Studio and an already bundled Advanced Editor.
// Node >= 18. The Advanced Editor (studio-offline.js) is maintained separately.
import {copyFileSync} from 'node:fs';
copyFileSync(new URL('./src/hybrid.js',import.meta.url),new URL('./dist/assets/hybrid.js',import.meta.url));
copyFileSync(new URL('./src/hybrid.css',import.meta.url),new URL('./dist/assets/hybrid.css',import.meta.url));
copyFileSync(new URL('./hybrid.html',import.meta.url),new URL('./dist/hybrid.html',import.meta.url));
console.log('V0.5 Hybrid front end built (static assets copied).');
