import { joinURL } from 'ufo'

export default defineEventHandler((event) => {
  const config = useRuntimeConfig()
  const proxyUrl = config.proxyUrl
  const path = event.path
  const target = joinURL(proxyUrl, path)
  console.log(`[NUXT] Proxying request to: ${target}`)

  return proxyRequest(event, target)
})
