export default defineAppConfig({
  ui: {
    colors: {
      primary: 'green',
      neutral: 'slate'
    },
    main: {
      base: 'min-h-[calc(100vh-var(--ui-header-height)-128px)]'
    },
    header: {
      slots: {
        toggle: 'hidden'
      }
    }
  }
})
