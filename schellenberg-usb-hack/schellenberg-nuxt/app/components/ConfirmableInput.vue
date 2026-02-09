<script lang="ts" setup>
const props = defineProps<{
  value: string | null
  placeholder?: string
}>()

const currentValue = ref(props.value || '')
const isModified = computed(() => currentValue.value?.length > 0 && currentValue.value !== props.value)

const emit = defineEmits(['confirm'])

const inputField = useTemplateRef('input')

const onSubmit = () => {
  emit('confirm', currentValue.value)
}
</script>

<template>
  <UForm
    class="flex items-center gap-1 w-full"
    @submit="onSubmit"
  >
    <UFormField
      class="w-full"
      name="name"
    >
      <UInput
        ref="input"
        v-model="currentValue"
        type="text"
        :placeholder="props.placeholder || 'unnamed'"
        size="lg"
        variant="ghost"
        class="mr-1 w-full"
      >
        <template #trailing>
          <UButton
            v-if="!isModified"
            type="button"
            color="warning"
            size="sm"
            icon="i-lucide-edit"
            variant="ghost"
            @click="inputField?.inputRef?.focus()"
          />
          <UButton
            v-else
            type="submit"
            color="primary"
            size="sm"
            icon="i-lucide-check"
          />
        </template>
      </UInput>
    </UFormField>
  </UForm>
</template>
