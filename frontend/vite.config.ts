import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env variables based on mode
  const env = loadEnv(mode, process.cwd(), '');
  
  return {
    base: './',
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      strictPort: true,
    },
    build: {
      outDir: 'build',
      emptyOutDir: true,
    },
    define: {
      // Explicitly define environment variables for production
      'process.env.NODE_ENV': JSON.stringify(mode),
      'import.meta.env.VITE_AUTH0_DOMAIN': JSON.stringify(env.VITE_AUTH0_DOMAIN || 'auth.denker.ai'),
      'import.meta.env.VITE_AUTH0_CLIENT_ID': JSON.stringify(env.VITE_AUTH0_CLIENT_ID || 'lq6uzeeUp9i14E8FNpJwr0DVIP5VtOzQ'),
      'import.meta.env.VITE_AUTH0_AUDIENCE': JSON.stringify(env.VITE_AUTH0_AUDIENCE || 'https://api.denker.ai'),
      'import.meta.env.VITE_NODE_ENV': JSON.stringify(mode),
    }
  };
}); 