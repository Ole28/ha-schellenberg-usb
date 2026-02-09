// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  modules: [
    '@nuxt/eslint',
    '@nuxt/ui',
    'nuxt-open-fetch',
    '@vueuse/nuxt',
    '@pinia/nuxt'
  ],
  ssr: false,

  devtools: {
    enabled: true
  },

  app: {
    baseURL: './',
    cdnURL: './'
  },
  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    proxyUrl: 'http://localhost:8000'
  },

  compatibilityDate: '2025-01-15',

  eslint: {
    config: {
      stylistic: {
        commaDangle: 'never',
        braceStyle: '1tbs'
      }
    }
  },
  openFetch: {
    clients: {
      schellenberg: {
        baseURL: 'http://localhost:3000/',
        schema: 'http://localhost:8000/openapi.json'
      }
    }
  }
})
