import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { viteStaticCopy } from "vite-plugin-static-copy";
import { resolve } from "path";
import fs from "fs";
import path from "path";

export default defineConfig(({ mode }) => ({
  base: "./",
  plugins: [
    svelte(),
    viteStaticCopy({
      targets: [
        {
          src: "public/*.png",
          dest: ".",
        },
        {
          src: "src/content/content.css",
          dest: ".",
        },
      ],
      hook: "writeBundle",
    }),
    {
      name: "ruh-manifest",
      closeBundle() {
        const srcPath = path.resolve(process.cwd(), "public/manifest.json");
        const destPath = path.resolve(process.cwd(), "dist/manifest.json");
        const manifest = JSON.parse(fs.readFileSync(srcPath, "utf-8"));

        if (mode === "production") {
          if (Array.isArray(manifest.host_permissions)) {
            manifest.host_permissions = manifest.host_permissions.filter(
              (p: string) => !p.includes("localhost"),
            );
          }
          if (manifest.content_security_policy?.extension_pages) {
            manifest.content_security_policy.extension_pages =
              manifest.content_security_policy.extension_pages.replace(
                /\s*http:\/\/localhost:\d+/g,
                "",
              );
          }
        }

        fs.writeFileSync(destPath, JSON.stringify(manifest, null, 2));
      },
    },
    {
      name: "move-sidepanel-html",
      closeBundle() {
        // Move sidepanel.html from dist/src/ to dist/ after build
        const srcPath = path.resolve(process.cwd(), "dist/src/sidepanel.html");
        const destPath = path.resolve(process.cwd(), "dist/sidepanel.html");
        if (fs.existsSync(srcPath)) {
          fs.renameSync(srcPath, destPath);
          // Remove empty src directory
          try {
            fs.rmdirSync(path.resolve(process.cwd(), "dist/src"));
          } catch (e) {
            // Directory might not be empty or might not exist
          }
        }
      },
    },
  ],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      // Use relative paths for assets in subdirectories
      makeAbsoluteExternalsRelative: true,
      input: {
        sidepanel: resolve(__dirname, "src/sidepanel.html"),
        content: resolve(__dirname, "src/content/content.ts"),
        background: resolve(__dirname, "src/background/background.ts"),
      },
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "[name].js",
        assetFileNames: (assetInfo) => {
          // Keep HTML files at root for side panel
          if (assetInfo.name?.endsWith(".html")) {
            return "[name][extname]";
          }
          return "assets/[name][extname]";
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
}));
