import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 로컬 실행 전제(§8.1). /api 는 FastAPI(8000)로 프록시한다.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.PNL_API_URL ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
