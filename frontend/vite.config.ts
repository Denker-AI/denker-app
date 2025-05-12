import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import dotenv from 'dotenv';

// Force load the appropriate .env file based on mode
const loadDotEnvFile = (mode) => {
  const envFile = mode === 'production' ? '.env.production' : '.env';
  console.log(`Loading environment from ${envFile} for ${mode} mode`);
  dotenv.config({ path: envFile });
};

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env variables based on mode
  loadDotEnvFile(mode);
  const env = loadEnv(mode, process.cwd(), '');
  
  // Log loaded variables (without sensitive values)
  console.log('Loaded environment variables:', {
    VITE_AUTH0_DOMAIN: env.VITE_AUTH0_DOMAIN,
    VITE_AUTH0_CLIENT_ID: env.VITE_AUTH0_CLIENT_ID ? env.VITE_AUTH0_CLIENT_ID.substring(0, 8) + '...' : 'MISSING',
    VITE_AUTH0_AUDIENCE: env.VITE_AUTH0_AUDIENCE,
    VITE_NODE_ENV: env.VITE_NODE_ENV || mode,
    NODE_ENV: process.env.NODE_ENV,
    mode: mode
  });
  
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
      'import.meta.env.VITE_NODE_ENV': JSON.stringify(env.VITE_NODE_ENV || mode),
    }
  };
}); 