<script setup lang="ts">
const props = defineProps <{ device: Sender, isPaired: boolean }>()

const devices = deviceStore()

const sorted = useSorted(props.device.connected_devices, (a, b) => a.enumerator.localeCompare(b.enumerator))
</script>

<template>
  <div
    v-for="connected_device in sorted"
    :key="connected_device.enumerator"
    class="flex gap-1 p-1 border rounded"
    :class="devices.deviceEvents.get(props.device.device_id)?.event.receiver === connected_device.enumerator ? 'border-4 border-green-500' : ''"
  >
    <ConfirmableInput
      :value="connected_device.name || ''"
      placeholder="unnamed receiver"
      @confirm="async (newName) => await devices.changeReceiverName(props.device.device_id, connected_device.enumerator, newName)"
    />
    <UButton
      color="error"
      size="sm"
      icon="i-fluent-delete-16-regular"
      variant="solid"
      @click="async () => await devices.deleteConnectedDevice(props.device.device_id, connected_device.enumerator)"
    />

    <UBadge
      color="neutral"
      variant="subtle"
      class="font-mono"
    >
      {{ connected_device.enumerator }}
    </UBadge>
    <PairModal
      v-if="!props.isPaired"
      :sender-name="props.device.name || ''"
      :receiver-id="props.device.device_id"
    >
      Pair
    </PairModal>
  </div>
</template>
