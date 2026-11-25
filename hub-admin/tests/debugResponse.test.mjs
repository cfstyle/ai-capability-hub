import assert from 'node:assert/strict'
import { test } from 'node:test'
import { formatResponse, responseCodeTokens } from '../src/views/tools/responseFormat.ts'

test('decodes the JSON text block returned by MCP without escaping its fields', () => {
  const result = { bond_code: '111', error: '未找到该债券', available_codes: ['019547'] }
  assert.deepEqual(formatResponse([JSON.stringify(result)]), {
    format: 'json',
    text: JSON.stringify(result, null, 2),
  })
})

test('keeps plain text, mixed content and empty results distinct', () => {
  assert.deepEqual(formatResponse(['{incomplete']), { format: 'text', text: '{incomplete' })
  assert.deepEqual(JSON.parse(formatResponse(['hello', '[true,0]']).text), ['hello', [true, 0]])
  assert.equal(formatResponse(0).text, '0')
  assert.equal(formatResponse(null).text, 'null')
  assert.equal(formatResponse(undefined), null)
})

test('highlights JSON tokens without changing the original text', () => {
  const text = '  {"key": "<script>\\\"</script>", "value": false, "count": -2.5e+10}'
  const tokens = responseCodeTokens(text, 'json')
  assert.equal(tokens.map((token) => token.text).join(''), text)
  assert.deepEqual(tokens.filter((token) => token.kind).map((token) => token.kind), [
    'key', 'string', 'key', 'literal', 'key', 'literal',
  ])
  assert.deepEqual(responseCodeTokens(text, 'text'), [{ text }])
})
