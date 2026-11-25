<template>
  <el-config-provider :locale="zhCn">
    <router-view />
    <MdSnackbar />
  </el-config-provider>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { useThemeStore } from '@/stores/theme'
import MdSnackbar from '@/components/m3/MdSnackbar.vue'

const themeStore = useThemeStore()

onMounted(() => {
  themeStore.initTheme()
})
</script>

<style>
/* Global resets handled in main.css */
</style>
