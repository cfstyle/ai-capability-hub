import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  argbFromHex,
  hexFromArgb,
  CorePalette,
  Hct,
  TonalPalette
} from '@material/material-color-utilities'

export type ThemeMode = 'light' | 'dark'
export type LayoutContext = 'admin' | 'portal'
export type DensityMode = 'comfortable' | 'compact'

export interface ThemePreset {
  id: string
  key: string
  name: string
  hex: string
  category: string
  description: string
  lowChroma?: boolean
  monochrome?: boolean
}

export type SeedPreset = ThemePreset

/**
 * M3 HCT 动态种子色调色板单一数据源
 * 仅保留 Studio 极简风（AI Studio 控制台高阶黑白灰极简），作为默认且唯一的平台风格
 */
export const THEME_PRESETS: ThemePreset[] = [
  {
    id: 'studio-monochrome',
    key: 'studio-monochrome',
    name: 'Studio 极简',
    hex: '#1F1F1F',
    category: '极简工程',
    description: 'AI Studio 控制台纯白极简风',
    monochrome: true
  }
]

export const SEED_PRESETS = THEME_PRESETS

const THEME_STORAGE_KEY = 'm3-theme'
const SEED_STORAGE_KEY = 'm3-seed-color'
const CONTEXT_STORAGE_KEY = 'm3-layout-context'
const DENSITY_STORAGE_KEY = 'm3-density'

// 防御性 Storage 访问封装（隔离无痕模式或禁用 Cookie 抛错）
const safeStorage = {
  getItem: (key: string): string | null => {
    try {
      return typeof window !== 'undefined' && window.localStorage ? window.localStorage.getItem(key) : null
    } catch {
      return null
    }
  },
  setItem: (key: string, value: string): void => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(key, value)
      }
    } catch {
      // 容错静默
    }
  }
}

const HEX_COLOR_REGEX = /^#[0-9A-Fa-f]{6}$/

export const useThemeStore = defineStore('theme', () => {
  const currentTheme = ref<ThemeMode>('light')
  const seedColor = ref<string>('#1F1F1F')
  const layoutContext = ref<LayoutContext>('admin')
  const density = ref<DensityMode>('comfortable')

  const isDark = computed(() => currentTheme.value === 'dark')

  /**
   * 基于官方 HCT 动态色彩算法计算并向 :root 注入完整 M3 变量
   * 严格遵循 M3 HCT 明度规范：浅色模式下所有 container 保持 Tone 90
   */
  const applyM3Theme = (seedHex: string, dark: boolean) => {
    try {
      // 防御校验输入是否为有效 6 位 Hex 格式
      const normalizedHex = HEX_COLOR_REGEX.test(seedHex) ? seedHex : '#6750A4'
      const argb = argbFromHex(normalizedHex)
      const corePalette = CorePalette.of(argb)

      const root = typeof document !== 'undefined' ? document.documentElement : null
      if (!root) return

      let p = corePalette.a1
      let s = corePalette.a2
      const t = corePalette.a3
      let n = corePalette.n1
      let nv = corePalette.n2
      const err = corePalette.error

      // 匹配当前主题预设，若标记 lowChroma 则手动构建低彩度调色板（覆盖 SchemeTonalSpot 强制的高彩度映射）
      const activePreset = THEME_PRESETS.find(
        (preset) => preset.hex.toLowerCase() === normalizedHex.toLowerCase()
      )

      if (activePreset?.monochrome) {
        // 使用 TonalPalette.fromHueAndChroma(0, 0) 生成纯粹的零彩度中性灰阶
        const mono = TonalPalette.fromHueAndChroma(0, 0)
        const monoTokens: Record<string, string> = dark
          ? {
              // 深色模式 (Dark Mode) - 纯零彩度中性灰阶 (R=G=B, 消除任何杂色偏色)
              '--md-sys-color-primary': '#E3E3E3',
              '--md-sys-color-on-primary': '#141414',
              '--md-sys-color-primary-container': '#262626',
              '--md-sys-color-on-primary-container': '#E3E3E3',
              '--md-sys-color-inverse-primary': '#141414',

              '--md-sys-color-secondary': '#C4C4C4',
              '--md-sys-color-on-secondary': '#141414',
              '--md-sys-color-secondary-container': '#262626',
              '--md-sys-color-on-secondary-container': '#E3E3E3',

              '--md-sys-color-tertiary': '#C4C4C4',
              '--md-sys-color-on-tertiary': '#141414',
              '--md-sys-color-tertiary-container': '#262626',
              '--md-sys-color-on-tertiary-container': '#E3E3E3',

              '--md-sys-color-error': hexFromArgb(err.tone(80)),
              '--md-sys-color-on-error': hexFromArgb(err.tone(20)),
              '--md-sys-color-error-container': hexFromArgb(err.tone(30)),
              '--md-sys-color-on-error-container': hexFromArgb(err.tone(90)),

              '--md-sys-color-surface': '#141414',
              '--md-sys-color-surface-dim': '#141414',
              '--md-sys-color-surface-bright': '#383838',
              '--md-sys-color-surface-container-lowest': '#0E0E0E',
              '--md-sys-color-surface-container-low': '#1C1C1C',
              '--md-sys-color-surface-container': '#242424',
              '--md-sys-color-surface-container-high': '#2B2B2B',
              '--md-sys-color-surface-container-highest': '#333333',

              '--md-sys-color-on-surface': '#E3E3E3',
              '--md-sys-color-on-surface-variant': '#C4C4C4',
              '--md-sys-color-outline': '#8E8E8E',
              '--md-sys-color-outline-variant': '#444444',
              '--md-sys-color-inverse-surface': '#E3E3E3',
              '--md-sys-color-inverse-on-surface': '#141414'
            }
          : {
              // 浅色模式 (Light Mode) - 纯零彩度中性灰阶 (彻底消除泛蓝与 slate 杂色)
              '--md-sys-color-primary': '#1F1F1F',
              '--md-sys-color-on-primary': '#FFFFFF',
              '--md-sys-color-primary-container': '#F0F0F0',
              '--md-sys-color-on-primary-container': '#1F1F1F',
              '--md-sys-color-inverse-primary': '#E3E3E3',

              '--md-sys-color-secondary': '#444444',
              '--md-sys-color-on-secondary': '#FFFFFF',
              '--md-sys-color-secondary-container': '#F0F0F0',
              '--md-sys-color-on-secondary-container': '#1F1F1F',

              '--md-sys-color-tertiary': '#444444',
              '--md-sys-color-on-tertiary': '#FFFFFF',
              '--md-sys-color-tertiary-container': '#F0F0F0',
              '--md-sys-color-on-tertiary-container': '#1F1F1F',

              '--md-sys-color-error': hexFromArgb(err.tone(40)),
              '--md-sys-color-on-error': hexFromArgb(err.tone(100)),
              '--md-sys-color-error-container': hexFromArgb(err.tone(90)),
              '--md-sys-color-on-error-container': hexFromArgb(err.tone(10)),

              '--md-sys-color-surface': '#FFFFFF',
              '--md-sys-color-surface-dim': '#F2F2F2',
              '--md-sys-color-surface-bright': '#FFFFFF',
              '--md-sys-color-surface-container-lowest': '#FFFFFF',
              '--md-sys-color-surface-container-low': '#F7F7F7',
              '--md-sys-color-surface-container': '#F0F0F0',
              '--md-sys-color-surface-container-high': '#EAEAEA',
              '--md-sys-color-surface-container-highest': '#E0E0E0',

              '--md-sys-color-on-surface': '#1F1F1F',
              '--md-sys-color-on-surface-variant': '#5F5F5F',
              '--md-sys-color-outline': '#757575',
              '--md-sys-color-outline-variant': '#E0E0E0',
              '--md-sys-color-inverse-surface': '#2E2E2E',
              '--md-sys-color-inverse-on-surface': '#F5F5F5'
            }

        for (const [varName, varVal] of Object.entries(monoTokens)) {
          root.style.setProperty(varName, varVal)
        }
        return
      }

      if (activePreset?.lowChroma) {
        const hct = Hct.fromInt(argb)
        // 主色板 primaryPalette: 使用 TonalPalette.fromHueAndChroma(hct.hue, 18)（克制的深藏青，而非艳蓝色）
        p = TonalPalette.fromHueAndChroma(hct.hue, 18)
        // 辅助色板 secondaryPalette: 使用 TonalPalette.fromHueAndChroma(hct.hue, 10)（冷灰石板蓝容器）
        s = TonalPalette.fromHueAndChroma(hct.hue, 10)
        // 中性色板 neutralPalette: 使用 TonalPalette.fromHueAndChroma(hct.hue, 4)
        n = TonalPalette.fromHueAndChroma(hct.hue, 4)
        // 中性变体 nv: 保持冷灰质感 (chroma 8)
        nv = TonalPalette.fromHueAndChroma(hct.hue, 8)
      }

      const tokens: Record<string, string> = dark
        ? {
            // Dark Mode Tokens
            '--md-sys-color-primary': hexFromArgb(p.tone(80)),
            '--md-sys-color-on-primary': hexFromArgb(p.tone(20)),
            '--md-sys-color-primary-container': hexFromArgb(p.tone(30)),
            '--md-sys-color-on-primary-container': hexFromArgb(p.tone(90)),
            '--md-sys-color-inverse-primary': hexFromArgb(p.tone(40)),

            '--md-sys-color-secondary': hexFromArgb(s.tone(80)),
            '--md-sys-color-on-secondary': hexFromArgb(s.tone(20)),
            '--md-sys-color-secondary-container': hexFromArgb(s.tone(30)),
            '--md-sys-color-on-secondary-container': hexFromArgb(s.tone(90)),

            '--md-sys-color-tertiary': hexFromArgb(t.tone(80)),
            '--md-sys-color-on-tertiary': hexFromArgb(t.tone(20)),
            '--md-sys-color-tertiary-container': hexFromArgb(t.tone(30)),
            '--md-sys-color-on-tertiary-container': hexFromArgb(t.tone(90)),

            '--md-sys-color-error': hexFromArgb(err.tone(80)),
            '--md-sys-color-on-error': hexFromArgb(err.tone(20)),
            '--md-sys-color-error-container': hexFromArgb(err.tone(30)),
            '--md-sys-color-on-error-container': hexFromArgb(err.tone(90)),

            '--md-sys-color-surface': hexFromArgb(n.tone(6)),
            '--md-sys-color-surface-dim': hexFromArgb(n.tone(6)),
            '--md-sys-color-surface-bright': hexFromArgb(n.tone(24)),
            '--md-sys-color-surface-container-lowest': hexFromArgb(n.tone(4)),
            '--md-sys-color-surface-container-low': hexFromArgb(n.tone(10)),
            '--md-sys-color-surface-container': hexFromArgb(n.tone(12)),
            '--md-sys-color-surface-container-high': hexFromArgb(n.tone(17)),
            '--md-sys-color-surface-container-highest': hexFromArgb(n.tone(22)),

            '--md-sys-color-on-surface': hexFromArgb(n.tone(90)),
            '--md-sys-color-on-surface-variant': hexFromArgb(nv.tone(80)),
            '--md-sys-color-outline': hexFromArgb(nv.tone(60)),
            '--md-sys-color-outline-variant': hexFromArgb(nv.tone(30)),
            '--md-sys-color-inverse-surface': hexFromArgb(n.tone(90)),
            '--md-sys-color-inverse-on-surface': hexFromArgb(n.tone(20))
          }
        : {
            // Light Mode Tokens (Tone 90 容器平衡规范)
            '--md-sys-color-primary': hexFromArgb(p.tone(40)),
            '--md-sys-color-on-primary': hexFromArgb(p.tone(100)),
            '--md-sys-color-primary-container': hexFromArgb(p.tone(90)),
            '--md-sys-color-on-primary-container': hexFromArgb(p.tone(10)),
            '--md-sys-color-inverse-primary': hexFromArgb(p.tone(80)),

            '--md-sys-color-secondary': hexFromArgb(s.tone(40)),
            '--md-sys-color-on-secondary': hexFromArgb(s.tone(100)),
            '--md-sys-color-secondary-container': hexFromArgb(s.tone(90)),
            '--md-sys-color-on-secondary-container': hexFromArgb(s.tone(10)),

            '--md-sys-color-tertiary': hexFromArgb(t.tone(40)),
            '--md-sys-color-on-tertiary': hexFromArgb(t.tone(100)),
            '--md-sys-color-tertiary-container': hexFromArgb(t.tone(90)),
            '--md-sys-color-on-tertiary-container': hexFromArgb(t.tone(10)),

            '--md-sys-color-error': hexFromArgb(err.tone(40)),
            '--md-sys-color-on-error': hexFromArgb(err.tone(100)),
            '--md-sys-color-error-container': hexFromArgb(err.tone(90)),
            '--md-sys-color-on-error-container': hexFromArgb(err.tone(10)),

            '--md-sys-color-surface': hexFromArgb(n.tone(98)),
            '--md-sys-color-surface-dim': hexFromArgb(n.tone(87)),
            '--md-sys-color-surface-bright': hexFromArgb(n.tone(98)),
            '--md-sys-color-surface-container-lowest': hexFromArgb(n.tone(100)),
            '--md-sys-color-surface-container-low': hexFromArgb(n.tone(96)),
            '--md-sys-color-surface-container': hexFromArgb(n.tone(94)),
            '--md-sys-color-surface-container-high': hexFromArgb(n.tone(92)),
            '--md-sys-color-surface-container-highest': hexFromArgb(n.tone(90)),

            '--md-sys-color-on-surface': hexFromArgb(n.tone(10)),
            '--md-sys-color-on-surface-variant': hexFromArgb(nv.tone(30)),
            '--md-sys-color-outline': hexFromArgb(nv.tone(50)),
            '--md-sys-color-outline-variant': hexFromArgb(nv.tone(80)),
            '--md-sys-color-inverse-surface': hexFromArgb(n.tone(20)),
            '--md-sys-color-inverse-on-surface': hexFromArgb(n.tone(95))
          }

      for (const [varName, varVal] of Object.entries(tokens)) {
        root.style.setProperty(varName, varVal)
      }
    } catch (e) {
      console.warn('Failed to apply M3 HCT dynamic theme:', e)
    }
  }

  const setTheme = (theme: ThemeMode) => {
    currentTheme.value = theme
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.theme = theme
    }
    safeStorage.setItem(THEME_STORAGE_KEY, theme)
    applyM3Theme(seedColor.value, theme === 'dark')
  }

  const toggleTheme = () => {
    setTheme(currentTheme.value === 'dark' ? 'light' : 'dark')
  }

  const setSeedColor = (hex: string) => {
    let validHex = HEX_COLOR_REGEX.test(hex) ? hex : '#6750A4'
    // 兼容历史机构藏青旧值 #1B4978 迁移至微调后的冷峻钢蓝 #1E3A5F
    if (validHex.toLowerCase() === '#1b4978') {
      validHex = '#1E3A5F'
    }
    seedColor.value = validHex
    safeStorage.setItem(SEED_STORAGE_KEY, validHex)
    applyM3Theme(validHex, isDark.value)
  }

  const setLayoutContext = (ctx: LayoutContext) => {
    layoutContext.value = ctx
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.context = ctx
    }
    safeStorage.setItem(CONTEXT_STORAGE_KEY, ctx)
  }

  const setDensity = (den: DensityMode) => {
    density.value = den
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.density = den
    }
    safeStorage.setItem(DENSITY_STORAGE_KEY, den)
  }

  const initTheme = () => {
    // 1. 初始化主题（明暗，带防御白名单校验）
    const savedTheme = safeStorage.getItem(THEME_STORAGE_KEY)
    if (savedTheme === 'dark' || savedTheme === 'light') {
      currentTheme.value = savedTheme
    } else {
      const prefersDark = typeof window !== 'undefined' && window.matchMedia
        ? window.matchMedia('(prefers-color-scheme: dark)').matches
        : false
      currentTheme.value = prefersDark ? 'dark' : 'light'
    }
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.theme = currentTheme.value
    }

    // 2. 初始化种子色（仅保留 Studio 极简风 #1F1F1F 为默认与唯一风格）
    seedColor.value = '#1F1F1F'
    safeStorage.setItem(SEED_STORAGE_KEY, '#1F1F1F')

    // 3. 初始化场景预设与密度（白名单校验）
    const savedContext = safeStorage.getItem(CONTEXT_STORAGE_KEY)
    if (savedContext === 'admin' || savedContext === 'portal') {
      layoutContext.value = savedContext
    }
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.context = layoutContext.value
    }

    const savedDensity = safeStorage.getItem(DENSITY_STORAGE_KEY)
    if (savedDensity === 'comfortable' || savedDensity === 'compact') {
      density.value = savedDensity
    }
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.density = density.value
    }

    // 4. 执行动态色板注入
    applyM3Theme(seedColor.value, currentTheme.value === 'dark')
  }

  return {
    currentTheme,
    isDark,
    seedColor,
    layoutContext,
    density,
    THEME_PRESETS,
    themePresets: THEME_PRESETS,
    seedPresets: THEME_PRESETS,
    toggleTheme,
    setTheme,
    setSeedColor,
    setLayoutContext,
    setDensity,
    applyM3Theme,
    initTheme
  }
})
