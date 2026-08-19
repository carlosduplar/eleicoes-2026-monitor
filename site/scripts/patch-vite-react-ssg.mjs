import { readdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
const packageRoot = join(process.cwd(), 'node_modules', 'vite-react-ssg');
const targetImport = "import('react-router-dom/server.js')";
const replacementImport = "import('react-router')";

async function patchDirectory(directory) {
  let patchedFiles = 0;
  const entries = await readdir(directory, { withFileTypes: true });

  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      patchedFiles += await patchDirectory(path);
      continue;
    }
    if (!entry.name.endsWith('.mjs')) {
      continue;
    }

    const source = await readFile(path, 'utf8');
    if (!source.includes(targetImport)) {
      continue;
    }

    await writeFile(path, source.replaceAll(targetImport, replacementImport));
    patchedFiles += 1;
  }

  return patchedFiles;
}

const patchedFiles = await patchDirectory(join(packageRoot, 'dist'));
console.log(`[postinstall] React Router v7 compatibility patch: ${patchedFiles} file(s) updated`);
