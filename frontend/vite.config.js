import { defineConfig } from 'vite';

export default defineConfig({
    root: '.',
    server: {
        port: 5173,
        proxy: {
            '/api': {
                target: process.env.DOCKER_ENV ? 'http://backend:8000' : 'http://localhost:8000',
                changeOrigin: true
            },
            '/ws': {
                target: process.env.DOCKER_ENV ? 'ws://backend:8000' : 'ws://localhost:8000',
                ws: true
            }
        }
    },
    build: {
        outDir: 'dist'
    },
    resolve: {
        alias: {
            '@': '/src'
        }
    }
})
