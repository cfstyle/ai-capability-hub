<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: number
    animated?: boolean
  }>(),
  {
    size: 28,
    animated: false
  }
)
</script>

<template>
  <div
    class="mcp-brand-logo"
    :class="{ 'is-animated': animated }"
    :style="{ width: `${size}px`, height: `${size}px` }"
  >
    <svg
      :width="size"
      :height="size"
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      class="mcp-logo-svg"
    >
      <defs>
        <!-- 主渐变：智能蓝紫 -> 活力青蓝 -->
        <linearGradient id="mcpGradPrimary" x1="4" y1="4" x2="44" y2="44" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#6366F1" />
          <stop offset="50%" stop-color="#3B82F6" />
          <stop offset="100%" stop-color="#06B6D4" />
        </linearGradient>

        <!-- 次渐变：用于高亮核心光晕 -->
        <linearGradient id="mcpGradAccent" x1="16" y1="16" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#38BDF8" />
          <stop offset="100%" stop-color="#818CF8" />
        </linearGradient>

        <!-- 柔和外发光滤镜 -->
        <filter id="mcpGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#3B82F6" flood-opacity="0.35" />
        </filter>
      </defs>

      <!-- 外层多边形轮廓 (Hexagon Shield 协议外框) -->
      <path
        d="M24 4.5L41.3205 14.5V34.5L24 44.5L6.67949 34.5V14.5L24 4.5Z"
        fill="url(#mcpGradPrimary)"
        fill-opacity="0.12"
        stroke="url(#mcpGradPrimary)"
        stroke-width="2.5"
        stroke-linejoin="round"
        filter="url(#mcpGlow)"
      />

      <!-- 三向智能聚合连接通道 (Model - Context - Protocol) -->
      <!-- 1. 顶部 Model 汇聚分支 -->
      <path
        d="M24 8V18"
        stroke="url(#mcpGradPrimary)"
        stroke-width="2.5"
        stroke-linecap="round"
      />
      <!-- 2. 左下 Context 汇聚分支 -->
      <path
        d="M11.5 31.5L20 26.5"
        stroke="url(#mcpGradPrimary)"
        stroke-width="2.5"
        stroke-linecap="round"
      />
      <!-- 3. 右下 Protocol 汇聚分支 -->
      <path
        d="M36.5 31.5L28 26.5"
        stroke="url(#mcpGradPrimary)"
        stroke-width="2.5"
        stroke-linecap="round"
      />

      <!-- 节点外圆环 -->
      <circle cx="24" cy="8" r="2.2" fill="#6366F1" />
      <circle cx="11.5" cy="31.5" r="2.2" fill="#06B6D4" />
      <circle cx="36.5" cy="31.5" r="2.2" fill="#3B82F6" />

      <!-- 中心智能枢纽 (MCP Core Hub) -->
      <path
        d="M24 18L29 24L24 30L19 24Z"
        fill="url(#mcpGradAccent)"
      />
      <!-- 核心晶体闪耀光点 -->
      <circle cx="24" cy="24" r="2" fill="#FFFFFF" />
    </svg>
  </div>
</template>

<style scoped>
.mcp-brand-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.mcp-brand-logo:hover {
  transform: scale(1.08) rotate(4deg);
}

.mcp-logo-svg {
  display: block;
}

.is-animated .mcp-logo-svg {
  animation: mcp-pulse 3s ease-in-out infinite alternate;
}

@keyframes mcp-pulse {
  0% {
    filter: drop-shadow(0 0 2px rgba(99, 102, 241, 0.3));
  }
  100% {
    filter: drop-shadow(0 0 8px rgba(6, 182, 212, 0.6));
  }
}
</style>
