import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(({ mode }) => ({ plugins: [react()], server: { host: '127.0.0.1', port: Number(loadEnv(mode, '.', '').VITE_DEV_PORT || 5173), strictPort: true }, build: { rollupOptions: { output: { manualChunks: { three: ['three'], react: ['react', 'react-dom'] } } } } }));
