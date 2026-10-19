#!/usr/bin/env node
// test-bundled-licences.mjs :: the licence plugin's own self-test, run by verify.sh after the
// dashboard's build. Usage: node scripts/test-bundled-licences.mjs [--case <what>] (after npm ci
// in frontend/)
//
// Each case is a small project built through Vite's API with frontend/bundled-licences.mjs, in a
// temporary folder that is removed afterwards. Packages that ship their licence must have it in the
// output: a scoped name, a CommonJS package, a font a stylesheet's url() brings in, a file small
// enough for Vite to inline, which must stay a file, a file a url() inlines on request, a
// stylesheet an @import brings in, a package a worker imports, a file the page's HTML brings in, a
// file a script's new URL() names and one it inlines through a template, which Vite imports, among
// them, with LICENSE, LICENCE.md, LICENSE.txt and COPYING each a licence file. The first case holds
// a licence file and the index to every character, with Vite's note, and a build with no helper of
// Vite's holds the index without it. A package with no licence file, or only files whose names hold
// a licence file's, one package name from two folders, a module, a url() file or a file a url()
// inlines on request from outside every package and the project, a module from a folder beside the
// project whose name begins with the project's, a build helper the plugin does not know, and a
// package's file the page's HTML or a script's new URL() inlines with ?inline, however written,
// must each stop the build with the plugin's message, naming the module where there is one.
// scripts/mutation-battery.mjs removes or loosens each of the plugin's guards in turn and names
// the case here that goes red; --case runs that case alone.
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  realpathSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const frontend = fileURLToPath(new URL('../frontend/', import.meta.url));
const viteDir = dirname(createRequire(join(frontend, 'package.json')).resolve('vite/package.json'));
const entry = JSON.parse(readFileSync(join(viteDir, 'package.json'), 'utf8')).exports['.'];
const vite = await import(
  pathToFileURL(join(viteDir, typeof entry === 'string' ? entry : (entry.import ?? entry.default)))
    .href
);
const { bundledLicences } = await import(
  pathToFileURL(join(frontend, 'bundled-licences.mjs')).href
);

// The folder's real path, as Vite resolves module ids, so a temporary folder behind a symlink,
// as on macOS, leaves the project root and its modules' ids alike.
const work = realpathSync(mkdtempSync(join(tmpdir(), 'licence-self-test-')));

// A project: its files, a package.json, an index.html that loads main.js, and Vite itself under
// node_modules, where the plugin finds Vite's licence for the helpers Vite writes.
function project(name, files) {
  const root = join(work, name, 'proj');
  for (const [path, text] of Object.entries(files)) {
    mkdirSync(dirname(join(root, path)), { recursive: true });
    writeFileSync(join(root, path), text);
  }
  mkdirSync(join(root, 'node_modules'), { recursive: true });
  symlinkSync(viteDir, join(root, 'node_modules/vite'), 'dir');
  writeFileSync(join(root, 'package.json'), '{"name":"case","private":true}');
  writeFileSync(
    join(root, 'index.html'),
    '<!doctype html><script type="module" src="./main.js"></script>',
  );
  return root;
}

const pkg = (name, license, extra = {}) => ({
  [`node_modules/${name}/package.json`]: JSON.stringify({
    name,
    version: '1.0.0',
    license,
    main: 'index.js',
  }),
  [`node_modules/${name}/index.js`]: 'export const v = 1;\n',
  ...extra,
});

async function build(root, plugins = [], config = {}) {
  const outDir = join(root, '../dist');
  try {
    await vite.build({
      root,
      configFile: false,
      logLevel: 'silent',
      build: { outDir, emptyOutDir: true },
      plugins: [...plugins, bundledLicences()],
      ...config,
    });
    return { outDir };
  } catch (error) {
    return { error: String(error.message) };
  }
}

// The index's opening line, and the note that follows it when Vite is listed.
const INDEX = 'Third-party packages in the Holly dashboard, their licence texts beside this file.';
const VITE_NOTE = ' Vite is here for the helper code it writes into the script.';

const shipped = (out, file) =>
  existsSync(join(out, file)) ? readFileSync(join(out, file), 'utf8') : '';
// Whether the output holds an SVG file, as an emitted file and not a data: URI.
const svgFiles = (out) =>
  existsSync(join(out, 'assets')) &&
  readdirSync(join(out, 'assets')).some((f) => f.endsWith('.svg'));
const refused = (result, words) =>
  result.error === undefined
    ? 'the build passed'
    : result.error.includes(words)
      ? null
      : `the build stopped without saying "${words}": ${result.error.slice(0, 160)}`;

const cases = [
  [
    "a package's licence ships, and Vite's for the helpers it writes",
    async () => {
      const files = pkg('goodpkg', 'MIT', {
        'node_modules/goodpkg/LICENSE': 'Synthetic MIT text\n',
      });
      files['main.js'] = "import { v } from 'goodpkg';\nconsole.log(v);\n";
      const { outDir, error } = await build(project('good', files));
      if (error) return error;
      const licence = shipped(outDir, 'licences/goodpkg.txt');
      if (licence !== 'goodpkg\nLicence: MIT\n\nSynthetic MIT text\n') {
        return `goodpkg.txt is ${JSON.stringify(licence)}`;
      }
      const index = shipped(outDir, 'licences/index.txt');
      if (index !== `${INDEX}${VITE_NOTE}\n\ngoodpkg: MIT\nvite: MIT\n`) {
        return `the index is ${JSON.stringify(index)}`;
      }
      return shipped(outDir, 'licences/vite.txt') ? null : 'no vite.txt';
    },
  ],
  [
    "a build with no helper of Vite's lists no Vite",
    async () => {
      const files = pkg('plainpkg', 'MIT', {
        'node_modules/plainpkg/LICENSE': 'Synthetic plain text\n',
      });
      files['main.js'] = "import { v } from 'plainpkg';\nconsole.log(v);\n";
      const noPolyfill = {
        name: 'case-no-polyfill',
        config: () => ({ build: { modulePreload: { polyfill: false } } }),
      };
      const { outDir, error } = await build(project('novite', files), [noPolyfill]);
      if (error) return error;
      const index = shipped(outDir, 'licences/index.txt');
      return index === `${INDEX}\n\nplainpkg: MIT\n`
        ? null
        : `the index is ${JSON.stringify(index)}`;
    },
  ],
  [
    'a package with no licence field ships its text, listed as see the text below',
    async () => {
      const files = pkg('nofield', undefined, {
        'node_modules/nofield/LICENSE': 'Synthetic text\n',
      });
      files['main.js'] = "import { v } from 'nofield';\nconsole.log(v);\n";
      const { outDir, error } = await build(project('nofield', files));
      if (error) return error;
      return shipped(outDir, 'licences/index.txt')
        .split('\n')
        .includes('nofield: see the text below')
        ? null
        : 'nofield is not listed as see the text below';
    },
  ],
  [
    "a scoped package's licence takes the __ name, and LICENCE.md counts",
    async () => {
      const files = pkg('@synthetic/pkg', 'MIT', {
        'node_modules/@synthetic/pkg/LICENCE.md': 'Synthetic text\n',
      });
      files['main.js'] = "import { v } from '@synthetic/pkg';\nconsole.log(v);\n";
      const { outDir, error } = await build(project('scoped', files));
      if (error) return error;
      return shipped(outDir, 'licences/@synthetic__pkg.txt') ? null : 'no @synthetic__pkg.txt';
    },
  ],
  [
    "a CommonJS package's helper modules count as that package, and COPYING counts",
    async () => {
      const files = {
        'node_modules/cjspkg/package.json': JSON.stringify({
          name: 'cjspkg',
          version: '2.0.0',
          license: 'ISC',
          main: 'index.js',
        }),
        'node_modules/cjspkg/index.js': 'module.exports = { v: 2 };\n',
        'node_modules/cjspkg/COPYING': 'Synthetic ISC text\n',
        'main.js': "import c from 'cjspkg';\nconsole.log(c.v);\n",
      };
      const { outDir, error } = await build(project('cjs', files));
      if (error) return error;
      return shipped(outDir, 'licences/index.txt').includes('cjspkg: ISC')
        ? null
        : 'cjspkg is not listed';
    },
  ],
  [
    "a font a stylesheet's url() brings in ships its package's licence",
    async () => {
      const files = {
        'node_modules/fontpkg/package.json': JSON.stringify({
          name: 'fontpkg',
          version: '1.0.0',
          license: 'OFL-1.1',
        }),
        'node_modules/fontpkg/files/x.woff2': 'synthetic font bytes ' + 'x'.repeat(8000),
        'node_modules/fontpkg/LICENSE': 'Synthetic OFL text\n',
        'style.css':
          "@font-face { font-family: X; src: url('fontpkg/files/x.woff2'); }\n" +
          'body { font-family: X; }\n',
        'main.js': "import './style.css';\nconsole.log(1);\n",
      };
      const { outDir, error } = await build(project('asset', files));
      if (error) return error;
      return shipped(outDir, 'licences/fontpkg.txt').includes('Synthetic OFL text')
        ? null
        : 'no fontpkg.txt';
    },
  ],
  [
    "a small file a stylesheet's url() brings in stays a file, and its licence ships",
    async () => {
      const files = {
        'node_modules/iconpkg/package.json': JSON.stringify({
          name: 'iconpkg',
          version: '1.0.0',
          license: 'MIT',
        }),
        'node_modules/iconpkg/files/i.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>\n',
        'node_modules/iconpkg/LICENSE.txt': 'Synthetic icon licence\n',
        'style.css': ".x { background-image: url('iconpkg/files/i.svg'); }\n",
        'main.js': "import './style.css';\nconsole.log(1);\n",
      };
      const { outDir, error } = await build(project('small', files));
      if (error) return error;
      if (!svgFiles(outDir)) return 'the file was inlined';
      return shipped(outDir, 'licences/iconpkg.txt').includes('Synthetic icon licence')
        ? null
        : 'no iconpkg.txt';
    },
  ],
  [
    "a package's file a url() inlines on request ships its licence",
    async () => {
      const files = pkg('inlinepkg', 'MIT', {
        'node_modules/inlinepkg/LICENSE': 'Synthetic inline licence\n',
        'node_modules/inlinepkg/i.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>\n',
        'style.css': ".x { background-image: url('inlinepkg/i.svg?inline'); }\n",
        'main.js': "import './style.css';\nconsole.log(1);\n",
      });
      const { outDir, error } = await build(project('inline', files));
      if (error) return error;
      if (svgFiles(outDir)) return 'the file was not inlined';
      return shipped(outDir, 'licences/inlinepkg.txt').includes('Synthetic inline licence')
        ? null
        : 'no inlinepkg.txt';
    },
  ],
  [
    "a package's stylesheet an @import brings in ships its licence",
    async () => {
      const files = pkg('csspkg', 'MIT', {
        'node_modules/csspkg/LICENSE': 'Synthetic stylesheet licence\n',
        'node_modules/csspkg/x.css': '.y { color: red; }\n',
        'style.css': "@import 'csspkg/x.css';\n.x { color: blue; }\n",
        'main.js': "import './style.css';\nconsole.log(1);\n",
      });
      const { outDir, error } = await build(project('import', files));
      if (error) return error;
      return shipped(outDir, 'licences/csspkg.txt').includes('Synthetic stylesheet licence')
        ? null
        : 'no csspkg.txt';
    },
  ],
  [
    'a package a worker imports ships its licence',
    async () => {
      const files = pkg('workerpkg', 'MIT', {
        'node_modules/workerpkg/LICENSE': 'Synthetic worker licence\n',
        'w.js': "import { v } from 'workerpkg';\nself.postMessage(v);\n",
        'main.js': "new Worker(new URL('./w.js', import.meta.url), { type: 'module' });\n",
      });
      const { outDir, error } = await build(project('worker', files));
      if (error) return error;
      return shipped(outDir, 'licences/workerpkg.txt').includes('Synthetic worker licence')
        ? null
        : 'no workerpkg.txt';
    },
  ],
  [
    "a package's file the page's HTML brings in ships its licence",
    async () => {
      const files = pkg('htmlpkg', 'MIT', {
        'node_modules/htmlpkg/LICENSE': 'Synthetic page licence\n',
        'node_modules/htmlpkg/i.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>\n',
        'main.js': 'console.log(1);\n',
      });
      const root = project('html', files);
      writeFileSync(
        join(root, 'index.html'),
        '<!doctype html><img src="./node_modules/htmlpkg/i.svg" alt="">' +
          '<script type="module" src="./main.js"></script>',
      );
      const { outDir, error } = await build(root);
      if (error) return error;
      return shipped(outDir, 'licences/htmlpkg.txt').includes('Synthetic page licence')
        ? null
        : 'no htmlpkg.txt';
    },
  ],
  [
    "a package's file a script's new URL() names ships its licence",
    async () => {
      const files = pkg('urlpkg', 'MIT', {
        'node_modules/urlpkg/LICENSE': 'Synthetic URL licence\n',
        'node_modules/urlpkg/i.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>\n',
        'main.js': "console.log(new URL('./node_modules/urlpkg/i.svg', import.meta.url).href);\n",
      });
      const { outDir, error } = await build(project('url', files));
      if (error) return error;
      return shipped(outDir, 'licences/urlpkg.txt').includes('Synthetic URL licence')
        ? null
        : 'no urlpkg.txt';
    },
  ],
  [
    "a package's file the page's HTML inlines with ?inline, however written, stops the build",
    async () => {
      // As written, with its characters as references, which Vite decodes, and a page that
      // writes a data: URI of its own, in capitals.
      const forms = ['?inline', '?x&amp;inline', '&#63;&#105;nline', 'DATA:'];
      for (const [n, query] of forms.entries()) {
        const files = pkg('pageinline', 'MIT', {
          'node_modules/pageinline/LICENSE': 'Synthetic page licence\n',
          'node_modules/pageinline/i.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>\n',
          'main.js': 'console.log(1);\n',
        });
        const root = project(`page-inline-${n}`, files);
        const src =
          query === 'DATA:' ? 'DATA:image/gif,x' : `./node_modules/pageinline/i.svg${query}`;
        writeFileSync(
          join(root, 'index.html'),
          `<!doctype html><img src="${src}" alt=""><script type="module" src="./main.js"></script>`,
        );
        const problem = refused(await build(root), "the dashboard's page holds a data: URI");
        if (problem) return `${query}: ${problem}`;
      }
      return null;
    },
  ],
  [
    "a package's file a script's new URL() inlines with ?inline, however written, stops the build",
    async () => {
      // Each kind of quote, with ?inline alone and after another query; new and URL on lines of
      // their own; a comment after URL or its bracket, which Vite reads past; a name a define
      // writes in; and, in TypeScript, which esbuild rewrites before Vite reads it, the name
      // bracketed, asserted, cast, checked with satisfies or joined from two strings. The plugin
      // reads what Vite wrote, so each must stop the build, naming the module.
      const f = './node_modules/urlinline/i.svg';
      const define = { define: { __CASE_FILE__: JSON.stringify(`${f}?inline`) } };
      const forms = [
        ['main.js', `new URL('${f}?inline', import.meta.url)`],
        ['main.js', `new URL("${f}?inline", import.meta.url)`],
        ['main.js', `new URL(\`${f}?inline\`, import.meta.url)`],
        ['main.js', `new URL('${f}?x&inline', import.meta.url)`],
        ['main.js', `new URL("${f}?x&inline", import.meta.url)`],
        ['main.js', `new URL(\`${f}?x&inline\`, import.meta.url)`],
        ['main.js', `new\n  URL('${f}?inline', import.meta.url)`],
        ['main.js', `new URL /* c */ ('${f}?inline', import.meta.url)`],
        ['main.js', `new URL(/* c */ '${f}?inline', import.meta.url)`],
        ['main.js', `new URL( // c\n  '${f}?inline', import.meta.url)`],
        ['main.js', 'new URL(__CASE_FILE__, import.meta.url)', define],
        ['u.ts', `new URL(('${f}?inline'), import.meta.url)`],
        ['u.ts', `new URL(<string>'${f}?inline', import.meta.url)`],
        ['u.ts', `new URL(('${f}?inline' as string), import.meta.url)`],
        ['u.ts', `new URL(('${f}?inline' satisfies string), import.meta.url)`],
        ['u.ts', `new URL('${f}' + '?inline', import.meta.url)`],
      ];
      for (const [n, [file, call, config]] of forms.entries()) {
        const files = pkg('urlinline', 'MIT', {
          'node_modules/urlinline/LICENSE': 'Synthetic URL licence\n',
          'node_modules/urlinline/i.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>\n',
          [file]: `console.log(${call}.href);\n`,
        });
        if (file !== 'main.js') files['main.js'] = `import './${file}';\n`;
        const problem = refused(
          await build(project(`url-inline-${n}`, files), [], config),
          `${file}" holds a new URL() of a data: URI`,
        );
        if (problem) return `${JSON.stringify(call)}: ${problem}`;
      }
      return null;
    },
  ],
  [
    "a package's file a script's new URL() inlines through a template ships its licence",
    async () => {
      // A template with a part that varies, which Vite turns into an import of each file it can
      // match, so the file is a module of the build.
      const files = pkg('globinline', 'MIT', {
        'node_modules/globinline/LICENSE': 'Synthetic template licence\n',
        'node_modules/globinline/i.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>\n',
        'main.js':
          "const n = 'i';\n" +
          'console.log(new URL(`./node_modules/globinline/${n}.svg?inline`, ' +
          'import.meta.url).href);\n',
      });
      const { outDir, error } = await build(project('template-inline', files));
      if (error) return error;
      return shipped(outDir, 'licences/globinline.txt').includes('Synthetic template licence')
        ? null
        : 'no globinline.txt';
    },
  ],
  [
    'one package name from two folders stops the build',
    async () => {
      const files = {
        ...pkg('dupe', 'MIT', { 'node_modules/dupe/LICENSE': 'Version one\n' }),
        ...pkg('other', 'MIT', { 'node_modules/other/LICENSE': 'Other\n' }),
        'node_modules/other/index.js': "import { v } from 'dupe';\nexport const w = v + 1;\n",
        'node_modules/other/node_modules/dupe/package.json': JSON.stringify({
          name: 'dupe',
          version: '2.0.0',
          license: 'Apache-2.0',
          main: 'index.js',
        }),
        'node_modules/other/node_modules/dupe/index.js': 'export const v = 2;\n',
        'node_modules/other/node_modules/dupe/LICENSE': 'Version two\n',
        'main.js': "import { v } from 'dupe';\nimport { w } from 'other';\nconsole.log(v, w);\n",
      };
      return refused(
        await build(project('dupe', files)),
        "is in the dashboard's bundle from two folders",
      );
    },
  ],
  [
    'a package without a licence file stops the build',
    async () => {
      const files = pkg('nolicence', 'MIT');
      files['main.js'] = "import { v } from 'nolicence';\nconsole.log(v);\n";
      return refused(
        await build(project('nolicence', files)),
        "nolicence is in the dashboard's bundle but ships no licence file",
      );
    },
  ],
  [
    'a package whose files only hold a licence file name stops the build',
    async () => {
      const files = pkg('lookalike', 'MIT', {
        'node_modules/lookalike/sublicense': 'Not a licence\n',
        'node_modules/lookalike/licence.js': 'export const x = 1;\n',
      });
      files['main.js'] = "import { v } from 'lookalike';\nconsole.log(v);\n";
      return refused(
        await build(project('lookalike', files)),
        "lookalike is in the dashboard's bundle but ships no licence file",
      );
    },
  ],
  [
    'a module from outside the project and every package stops the build',
    async () => {
      mkdirSync(join(work, 'outside', 'elsewhere'), { recursive: true });
      writeFileSync(join(work, 'outside', 'elsewhere', 'x.js'), 'export const v = 3;\n');
      const files = { 'main.js': "import { v } from '../elsewhere/x.js';\nconsole.log(v);\n" };
      return refused(
        await build(project('outside', files)),
        `elsewhere/x.js" is in the dashboard's bundle but belongs to no package`,
      );
    },
  ],
  [
    'a file from outside the project and every package that a url() brings in stops the build',
    async () => {
      mkdirSync(join(work, 'outside-file', 'elsewhere'), { recursive: true });
      writeFileSync(
        join(work, 'outside-file', 'elsewhere', 'i.svg'),
        '<svg xmlns="http://www.w3.org/2000/svg"/>\n',
      );
      const files = {
        'style.css': ".x { background-image: url('../elsewhere/i.svg'); }\n",
        'main.js': "import './style.css';\nconsole.log(1);\n",
      };
      return refused(
        await build(project('outside-file', files)),
        `elsewhere/i.svg" is in the dashboard's bundle but belongs to no package`,
      );
    },
  ],
  [
    'a url() that inlines a file from outside the project and every package stops the build',
    async () => {
      mkdirSync(join(work, 'outside-inline', 'elsewhere'), { recursive: true });
      writeFileSync(
        join(work, 'outside-inline', 'elsewhere', 'i.svg'),
        '<svg xmlns="http://www.w3.org/2000/svg"/>\n',
      );
      const files = {
        'style.css': ".x { background-image: url('../elsewhere/i.svg?inline'); }\n",
        'main.js': "import './style.css';\nconsole.log(1);\n",
      };
      return refused(
        await build(project('outside-inline', files)),
        `elsewhere/i.svg?inline" is in the dashboard's bundle but belongs to no package`,
      );
    },
  ],
  [
    "a module from a folder whose name begins with the project's stops the build",
    async () => {
      mkdirSync(join(work, 'sibling', 'proj-next'), { recursive: true });
      writeFileSync(join(work, 'sibling', 'proj-next', 'x.js'), 'export const v = 5;\n');
      const files = { 'main.js': "import { v } from '../proj-next/x.js';\nconsole.log(v);\n" };
      return refused(
        await build(project('sibling', files)),
        `proj-next/x.js" is in the dashboard's bundle but belongs to no package`,
      );
    },
  ],
  [
    'a build helper the plugin does not know stops the build',
    async () => {
      const helper = {
        name: 'case-helper',
        resolveId: (id) => (id === 'virtual:helper' ? '\0case-helper.js' : null),
        load: (id) => (id === '\0case-helper.js' ? 'export default 4;' : null),
      };
      const files = { 'main.js': "import h from 'virtual:helper';\nconsole.log(h);\n" };
      return refused(
        await build(project('helper', files), [helper]),
        `case-helper.js" is in the dashboard's bundle but belongs to no package`,
      );
    },
  ],
];

const pick = process.argv[2] === '--case' ? process.argv[3] : undefined;
const chosen = cases.filter(([what]) => pick === undefined || what === pick);
if (chosen.length === 0) {
  rmSync(work, { recursive: true, force: true });
  console.log(`licence self-test: no case is called ${JSON.stringify(pick)}`);
  process.exit(1);
}
let bad = 0;
try {
  for (const [what, run] of chosen) {
    const problem = await run();
    if (problem) bad += 1;
    console.log(`${problem ? 'FAIL' : 'ok'}: ${what}${problem ? `: ${problem}` : ''}`);
  }
} finally {
  rmSync(work, { recursive: true, force: true });
}
if (bad > 0) {
  console.log(`licence self-test: ${bad} of ${chosen.length} cases misbehaved`);
  process.exit(1);
}
console.log(
  `licence self-test: ${chosen.length === 1 ? 'the case' : `all ${chosen.length} cases`} behaved`,
);
