import { readFile, readdir, unlink } from "node:fs/promises";

// The Python image copies dist verbatim, including existing non-client sidecars.
// Clean only obsolete hashed client JS/CSS after Vite has written its new index.
const dist = new URL("../dist/", import.meta.url);
const html = await readFile(new URL("index.html", dist), "utf8");
const referenced = new Set(html.match(/assets\/index-[\w-]+\.(?:js|css)/g));
if (!referenced.size)
  throw new Error("No client assets found in built index; refusing cleanup");
for (const name of await readdir(new URL("assets/", dist))) {
  if (
    /^index-[\w-]+\.(?:js|css)$/.test(name) &&
    !referenced.has(`assets/${name}`)
  ) {
    await unlink(new URL(`assets/${name}`, dist));
  }
}
