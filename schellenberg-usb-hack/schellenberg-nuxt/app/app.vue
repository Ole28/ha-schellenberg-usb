<template>
  <UApp>
    <UHeader mode="slideover">
      <template #left>
        <NuxtLink
          to="/"
          class="flex items-center w-72"
        >
          <AppLogo class="w-12 h-12 shrink-0" />
          <h1 class="ml-2 font-semibold text-xl">Schellenberg USB hack</h1>
        </NuxtLink>
      </template>

      <template #right>
        <UColorModeButton />
      </template>
    </UHeader>

    <UMain>
      <NuxtPage class="p-2" />
    </UMain>

    <USeparator icon="i-simple-icons-nuxtdotjs" />

    <UFooter>
      <template #default>
        <p class="text-muted text-sm">
          Built with Nuxt UI • © {{ new Date().getFullYear() }}
        </p>
      </template>
    </UFooter>
  </UApp>
</template>
