<script setup lang="ts">
const props = defineProps<{ device: Sender, isPaired: boolean }>()

const devices = deviceStore()
</script>

<template>
  <div class="border rounded">
    <div class="flex justify-between">
      <ConfirmableInput
        :value="props.device.name || ''"
        placeholder="unnamed sender"
        @confirm="async (newName) => await devices.changeSenderName(props.device.device_id, newName)"
      />
      <UBadge
        variant="subtle"
        color="neutral"
        class="font-mono"
      >
        {{ props.device.device_id }}
      </UBadge>
    </div>
    <USeparator class="m-2 w-full" />
    <div
      v-if="devices.deviceEvents.get(props.device.device_id)"
      class="mx-4 mb-2"
    >
      Last event: <UBadge class="font-mono">
        {{ devices.deviceEvents.get(props.device.device_id)?.event.command }}
        ({{ devices.deviceEvents.get(props.device.device_id)?.event.receiver }})
      </UBadge>
      at <UBadge
        class="font-mono"
        color="neutral"
      >
        {{ devices.deviceEvents.get(props.device.device_id)?.timestamp.toLocaleTimeString() || '-' }}
      </UBadge>
    </div>
    <div class="mx-4">
      Connected receivers:
      <div
        v-if="props.device.connected_devices.length > 0"
      >
        <ConnectedDevices
          :device="props.device"
          :is-paired="props.isPaired"
        />
      </div>
      <div
        v-else
        class="ml-4 italic"
      >
        No connected devices
      </div>
    </div>
  </div>
</template>
