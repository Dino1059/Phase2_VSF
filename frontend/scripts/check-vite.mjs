import { accessSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const viteJs = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "node_modules",
  "vite",
  "bin",
  "vite.js",
);

try {
  accessSync(viteJs);
} catch {
  console.error(
    "Vite is not installed in frontend/node_modules.\n" +
      "From frontend/ run:\n" +
      "  pnpm install --ignore-workspace --no-frozen-lockfile\n",
  );
  process.exit(1);
}
