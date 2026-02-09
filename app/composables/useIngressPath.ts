export const useIngressPath = () => {
  const config = useRuntimeConfig()

  const loadIngressPath = async () => {
    try {
      const { ingressPath } = await $fetch('./api/ingress-path')
      if (ingressPath) {
        config.public.openFetch.schellenberg.baseURL = ingressPath
        console.log(`Client using ingress path: ${ingressPath}`)
      }
    } catch (error) {
      console.error('Failed to load ingress path:', error)
    }
  }

  return { loadIngressPath }
}
