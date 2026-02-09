import { getRequestHeader } from 'h3'

export default defineEventHandler((event) => {
  const ingressPath = getRequestHeader(event, 'X-Ingress-Path')
  return {
    ingressPath: ingressPath || null
  }
})
