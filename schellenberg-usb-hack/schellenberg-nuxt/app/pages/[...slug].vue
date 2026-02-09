<template>
  <div>
    <div class="flex justify-end w-full">
      <UButton
        icon="i-fluent-arrow-sync-16-regular"
        @click="() => devices.refreshDevices()"
      >
        Refresh devices
      </UButton>
    </div>

    <div v-if="devices.devices.length">
      <SenderDevice
        v-if="devices.self"
        :is-paired="true"
        :device="devices.self"
        class="bg-accented mt-2 p-2 border-2 border-primary"
      />
      <USeparator
        v-if="devices.self"
        class="my-2 w-full"
      />
      <SenderDevice
        v-for="device in devices.otherDevices"
        :key="device.device_id"
        :device="device"
        :is-paired="false"
        class="my-1 p-2"
      />
    </div>
    <div
      v-else
      class="flex justify-center items-center h-32"
    >
      <p class="italic">
        No devices found.
      </p>
    </div>
  </div>
</template>

<script lang="ts" setup>
const devices = deviceStore()
</script>
