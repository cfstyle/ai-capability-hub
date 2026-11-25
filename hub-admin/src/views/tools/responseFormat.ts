export function formatResponse(result: unknown): { format: 'json' | 'text'; text: string } | null {
  if (result === undefined || result === '') return null

  // Hub puts the tool's text content into an array.
  const value = Array.isArray(result)
    ? result.length === 1 && typeof result[0] === 'string'
      ? decodeContent(result[0])
      : result.map(decodeContent)
    : decodeContent(result)

  if (typeof value === 'string') return value ? { format: 'text', text: value } : null
  return { format: 'json', text: JSON.stringify(value, null, 2) }
}

function decodeContent(content: unknown): unknown {
  if (typeof content !== 'string' || !/^\s*[\[{]/.test(content)) return content
  try {
    return JSON.parse(content)
  } catch {
    return content
  }
}

interface ResponseToken {
  text: string
  kind?: 'key' | 'string' | 'literal'
}

export function responseCodeTokens(text: string, format: 'json' | 'text'): ResponseToken[] {
  if (format === 'text' || text.length > 50_000) return [{ text }]

  const tokens: ResponseToken[] = []
  const pattern = /("(?:[^"\\]|\\.)*")(\s*:)?|(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?|true|false|null)/gi
  let offset = 0
  for (const match of text.matchAll(pattern)) {
    if (match.index > offset) tokens.push({ text: text.slice(offset, match.index) })
    if (match[1]) {
      tokens.push({ text: match[1], kind: match[2] ? 'key' : 'string' })
      if (match[2]) tokens.push({ text: match[2] })
    } else {
      tokens.push({ text: match[0], kind: 'literal' })
    }
    offset = match.index + match[0].length
  }
  if (offset < text.length) tokens.push({ text: text.slice(offset) })
  return tokens
}
