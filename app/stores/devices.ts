import type { SchellenbergResponse } from '#open-fetch'

export type Sender = SchellenbergResponse<'get_devices_api_devices_all_get'>['senders'][number]
type Event = {
  sender: {
    device_id: string
    name: string
  }
  receiver: number
  command: string
  counter: number
  local_counter: number
  signal_strength: number
}

const debounceRefresh = useDebounceFn(() => {
  deviceStore().refreshDevices()
}, 1000)

const { loadIngressPath } = useIngressPath()
await loadIngressPath()

const runtimeConfig = useRuntimeConfig()

export const deviceStore = defineStore('devices', () => {
  const { $schellenberg } = useNuxtApp()

  const { data, refresh: refreshDevices } = useSchellenberg('/api/devices/all')
  const devices = computed<Sender[]>(() => data.value?.senders || [])
  const deviceEvents = reactive<Map<string, { timestamp: Date, event: Event }>>(new Map())
  const self = computed<Sender | undefined>(() => {
    return devices.value.find(device => device.device_id === data.value?.self_sender_id)
  })
  const otherDevices = computed(() => devices.value.sort((a, b) => {
    const timestampA = deviceEvents.get(a.device_id)?.timestamp.getTime() || 0
    const timestampB = deviceEvents.get(b.device_id)?.timestamp.getTime() || 0
    if (timestampA == 0 && timestampB == 0) {
      return b.name?.localeCompare(a.name || '') || 0
    } else return timestampB - timestampA
  }).filter(device => device.device_id !== self.value?.device_id))

  let deviceEventsListener = new EventSource(runtimeConfig.public.openFetch.schellenberg.baseURL + 'api/devices/events')

  deviceEventsListener.onmessage = (event: MessageEvent<string>) => {
    const eventData = JSON.parse(event.data) as Event
    deviceEvents.set(eventData.sender.device_id, { timestamp: new Date(), event: eventData })
    debounceRefresh()
  }

  deviceEventsListener.onerror = async () => {
    console.error('Error in device events stream.')
    deviceEventsListener.close()
    await new Promise(resolve => setTimeout(resolve, 1000))
    deviceEventsListener = new EventSource('/api/devices/events')
  }

  function changeSenderName(senderId: string, newName: string) {
    console.log(`Changing name of sender ${senderId} to ${newName}`)
    return $schellenberg(`/api/devices/specific/{sender_id}/rename`, {
      method: 'POST',
      path: { sender_id: senderId },
      query: { new_name: newName }
    }).then(() => refreshDevices())
  }

  function changeReceiverName(senderId: string, receiverEnumerator: string, newName: string) {
    console.log(`Changing name of receiver ${receiverEnumerator} (sender ${senderId}) to ${newName}`)
    return $schellenberg(`/api/devices/specific/{sender_id}/{enumerator}/rename`, {
      method: 'POST',
      path: { sender_id: senderId, enumerator: receiverEnumerator },
      query: { new_name: newName }
    }).then(() => refreshDevices())
  }

  function pair(receiverId: string, newEnumerator: string) {
    return $schellenberg(`/api/devices/specific/{receiver_id}/{enumerator}/pair`, {
      method: 'POST',
      path: {
        receiver_id: receiverId,
        enumerator: newEnumerator
      }
    }).then((value) => {
      refreshDevices()
      return value
    })
  }

  function deleteConnectedDevice(receiverId: string, enumerator: string) {
    return $schellenberg(`/api/devices/specific/{sender_id}/{enumerator}/remove`, {
      method: 'POST',
      path: {
        sender_id: receiverId,
        enumerator
      }
    }).then(() => refreshDevices())
  }

  return { devices, self, otherDevices, refreshDevices, changeSenderName, changeReceiverName, deleteConnectedDevice, pair, deviceEvents }
})
