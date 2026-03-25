/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEFAULT_SYMBOL: string
  readonly VITE_DEFAULT_TIMEFRAME: string
  readonly VITE_REFRESH_INTERVAL: string
  readonly VITE_SUPABASE_URL: string
  readonly VITE_SUPABASE_ANON_KEY: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
