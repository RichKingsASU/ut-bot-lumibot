/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEFAULT_SYMBOL: string
  readonly VITE_DEFAULT_TIMEFRAME: string
  readonly VITE_REFRESH_INTERVAL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
