import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { viteStaticCopy } from 'vite-plugin-static-copy';
import { resolve } from 'path';
import fs from 'fs';
import path from 'path';

export default defineConfig({
  base: './',
  plugins: [
    svelte(),
    viteStaticCopy({
      targets: [
        {
          src: 'public/manifest.json',
          dest: '.'
        },
        {
          src: 'public/*.png',
          dest: '.'
        },
        {
          src: 'src/content/content.css',
          dest: '.'
        }
      ],
      hook: 'writeBundle'
    }),
    {
      name: 'move-sidepanel-html',
      closeBundle() {
        // Move sidepanel.html from dist/src/ to dist/ after build
        const srcPath = path.resolve(process.cwd(), 'dist/src/sidepanel.html');
        const destPath = path.resolve(process.cwd(), 'dist/sidepanel.html');
        if (fs.existsSync(srcPath)) {
          fs.renameSync(srcPath, destPath);
          // Remove empty src directory
          try {
            fs.rmdirSync(path.resolve(process.cwd(), 'dist/src'));
          } catch (e) {
            // Directory might not be empty or might not exist
          }
        }
      }
    }
  ],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      // Use relative paths for assets in subdirectories
      makeAbsoluteExternalsRelative: true,
      input: {
        sidepanel: resolve(__dirname, 'src/sidepanel.html'),
        content: resolve(__dirname, 'src/content/content.ts'),
        background: resolve(__dirname, 'src/background/background.ts')
      },
      output: {
        entryFileNames: '[name].js',
        chunkFileNames: '[name].js',
        assetFileNames: (assetInfo) => {
          // Keep HTML files at root for side panel
          if (assetInfo.name?.endsWith('.html')) {
            return '[name][extname]';
          }
          return 'assets/[name][extname]';
        }
      }
    }
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  }
});
