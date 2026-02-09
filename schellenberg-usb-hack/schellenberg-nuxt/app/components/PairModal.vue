<script setup lang="ts">
const devices = deviceStore()

const props = defineProps<{ receiverId: string, senderName: string }>()

const newEnumerator = ref('')

const open = ref(false)

const pending = ref(false)

function reset() {
  newEnumerator.value = ''
}

async function pair() {
  if (!newEnumerator.value) {
    alert('Please enter a new enumerator.')
    return
  }

  const enumeratorNumber = parseInt(newEnumerator.value, 16)
  if (isNaN(enumeratorNumber) || enumeratorNumber < 0x00 || enumeratorNumber > 0xFF) {
    alert('Please enter a valid hexadecimal number between 0x00 and 0xFF.')
    return
  }
  pending.value = true
  const res = await devices.pair(props.receiverId, newEnumerator.value)
  pending.value = false
  if (!res) {
    if (open.value) alert('Pairing failed. Please try again.')
    return
  }
  reset()
  open.value = false
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Pair new Device"
  >
    <UButton
      label="Pair"
      color="primary"
      size="sm"
      icon="i-fluent-plug-connected-add-20-regular"
    />

    <template #body>
      <UForm @submit="pair">
        <UFormField
          name="enumerator"
          label="New Enumerator (hex: 0x00 - 0xFF)"
        >
          <UInput
            v-model="newEnumerator"
            placeholder="Enter the new enumerator (hex 0x00 - 0xFF)"
            :disabled="pending"
            class="w-full"
          />
        </UFormField>
      </UForm>
      <h2
        v-if="pending"
        class="mt-4 font-bold text-lg"
      >
        Enable Programming Mode on the Sender {{ props.senderName }} <br>
        and press the STOP Button on the Sender within the next 30 seconds.
      </h2>
    </template>

    <template #footer>
      <div class="flex justify-between gap-2 w-full">
        <UButton
          label="Cancel"
          color="neutral"
          @click="open = false"
        />
        <UButton
          label="Pair"
          type="submit"
          color="primary"
          icon="i-fluent-plug-connected-add-20-regular"
          :loading="pending"
          @click="pair"
        />
      </div>
    </template>
  </UModal>
</template>
