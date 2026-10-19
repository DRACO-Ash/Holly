// bundled-licences.mjs :: ships the licence of every third-party package in the dashboard's build.
// Vite runs it once per production build. Each package with a module in the build's module
// graph, or a file the build records reading (a font or image a stylesheet's url() brings in,
// inlined or not, a stylesheet's @import, a worker's modules, the original of any file in the
// output), has its licence text copied to licences/<package>.txt in the build output, which the
// image serves beside the dashboard, and licences/index.txt lists them all, without versions,
// which attribution does not need. Vite counts too, for the helper code it writes into the script
// bundle. A package with no licence file, one package name from two folders, or a module or file
// that belongs neither to a package nor to the dashboard's own source, fails the build, so nothing
// ships without its terms. So does a data: URI in the built page, or in a script's new URL() once
// Vite has rewritten it, the two places Vite writes a file the page or the call names with ?inline
// into the output without recording that it read it: what is read is what Vite wrote, however the
// page or the script wrote the name, and a data: URI written there by hand stops the build too.
import { readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, isAbsolute, join } from "node:path";

const MODULES = "/node_modules/";
const LICENCE_FILE = /^(licen[cs]e|copying)(\.(md|txt))?$/i;
// Vite's module-preload polyfill and the CommonJS helpers of the plugin it bundles, both under
// Vite's licence file.
const VITE_HELPER = /^\0(vite\/|commonjsHelpers\.js$)/;
// What Vite writes in place of a new URL() whose file it inlines: the file as a data: URI, quoted
// by JSON.stringify.
const INLINED_URL = 'new URL("data:';

// The package a module id belongs to, with its folder: the name after the id's last node_modules,
// with its scope. null is the dashboard's own source, under the project root; undefined is a
// module from anywhere else. A helper module's id starts with a NUL byte, which is not part of
// the path.
function packageOf(id, root) {
  if (VITE_HELPER.test(id)) {
    const manifest = createRequire(join(root, "package.json")).resolve("vite/package.json");
    return { name: "vite", dir: dirname(manifest) };
  }
  const path = id.replace(/^\0/, "").replaceAll("\\", "/");
  const at = path.lastIndexOf(MODULES);
  if (at === -1) return path.startsWith(`${root}/`) ? null : undefined;
  const parts = path.slice(at + MODULES.length).split("/");
  const name = parts[0].startsWith("@") ? `${parts[0]}/${parts[1]}` : parts[0];
  return { name, dir: path.slice(0, at + MODULES.length) + name };
}

// The file name a package's licence takes in the output: a scope's slash becomes "__".
export const licenceFileName = (name) => `licences/${name.replace("/", "__")}.txt`;

export function bundledLicences() {
  let root = "";
  return {
    name: "holly-bundled-licences",
    apply: "build",
    // Vite inlines no file on its own, so a font stays a file of the output: the page's policy
    // takes fonts from 'self' only, not from data: URIs.
    config: () => ({ build: { assetsInlineLimit: 0 } }),
    configResolved(config) {
      root = config.root.replaceAll("\\", "/");
    },
    transform: {
      order: "post",
      handler(code, id) {
        if (code.includes(INLINED_URL)) {
          this.error(
            `${JSON.stringify(id)} holds a new URL() of a data: URI, as Vite writes a file ` +
              "inlined with ?inline, unrecorded, so its package's licence would not ship",
          );
        }
      },
    },
    transformIndexHtml: {
      order: "post",
      handler(html) {
        if (/data:/i.test(html)) {
          throw new Error(
            "the dashboard's page holds a data: URI, a file Vite wrote into it unrecorded, so " +
              "its package's licence would not ship",
          );
        }
      },
    },
    generateBundle() {
      const packages = new Map();
      const note = (found, source) => {
        if (found === undefined) {
          this.error(
            `${JSON.stringify(source)} is in the dashboard's bundle but belongs to no package`,
          );
        }
        if (!found) return;
        const seen = packages.get(found.name);
        if (seen !== undefined && seen !== found.dir) {
          this.error(
            `${found.name} is in the dashboard's bundle from two folders: ${seen}, ${found.dir}`,
          );
        }
        packages.set(found.name, found.dir);
      };
      for (const id of this.getModuleIds()) note(packageOf(id, root), id);
      // Every file the build records reading, which no module id need name: a stylesheet's
      // @import, a file a url() brings in, a worker's modules, and the original of each file in
      // the output, which Vite gives by its path from the project root.
      for (const file of this.getWatchFiles()) {
        note(packageOf(isAbsolute(file) ? file : join(root, file), root), file);
      }
      const index = [];
      // By UTF-16 code unit, as sort() orders by default, so the index stays byte for byte the
      // same: a locale's order would put "_" before "-".
      for (const name of [...packages.keys()].sort((a, b) => (a < b ? -1 : Number(a > b)))) {
        const dir = packages.get(name);
        const meta = JSON.parse(readFileSync(join(dir, "package.json"), "utf8"));
        const file = readdirSync(dir).find((f) => LICENCE_FILE.test(f));
        if (!file) this.error(`${name} is in the dashboard's bundle but ships no licence file`);
        const licence = typeof meta.license === "string" ? meta.license : "see the text below";
        const text = readFileSync(join(dir, file), "utf8");
        this.emitFile({
          type: "asset",
          fileName: licenceFileName(name),
          source: `${name}\nLicence: ${licence}\n\n${text}`,
        });
        index.push(`${name}: ${licence}`);
      }
      this.emitFile({
        type: "asset",
        fileName: "licences/index.txt",
        source:
          "Third-party packages in the Holly dashboard, their licence texts beside this file." +
          (packages.has("vite")
            ? " Vite is here for the helper code it writes into the script."
            : "") +
          `\n\n${index.join("\n")}\n`,
      });
    },
  };
}
