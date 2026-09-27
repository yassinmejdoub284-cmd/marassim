import { defineConfig } from 'vite';
export default defineConfig({ base: './', server: {
  host: '127.0.0.1', port: 5173, strictPort: true,
  proxy: { '/api': 'http://127.0.0.1:18744' },
  watch: { ignored: ['**/server-build/**', '**/server-dist/**', '**/release/**', '**/test-results/**', '**/.python-build/**'] }
} });
