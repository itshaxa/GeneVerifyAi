/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the GeneVerify backend API, including the versioned prefix. */
  readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
