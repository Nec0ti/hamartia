const assert = require('node:assert/strict')
const test = require('node:test')
const { inflateSync } = require('node:zlib')
const { onePixelPng } = require('./smokeFixtures.cjs')

function crc32(buffer) {
  let crc = 0xffffffff
  for (const byte of buffer) {
    crc ^= byte
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0)
  }
  return (crc ^ 0xffffffff) >>> 0
}

test('browser image fixture has valid PNG chunk CRCs and decodes to one pixel', () => {
  assert.deepEqual(onePixelPng.subarray(0, 8), Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
  let offset = 8
  let width
  let height
  let idat = Buffer.alloc(0)
  while (offset < onePixelPng.length) {
    const length = onePixelPng.readUInt32BE(offset)
    const type = onePixelPng.subarray(offset + 4, offset + 8)
    const data = onePixelPng.subarray(offset + 8, offset + 8 + length)
    const expectedCrc = onePixelPng.readUInt32BE(offset + 8 + length)
    assert.equal(crc32(Buffer.concat([type, data])), expectedCrc, `${type.toString()} chunk CRC`)
    if (type.toString() === 'IHDR') {
      width = data.readUInt32BE(0)
      height = data.readUInt32BE(4)
    }
    if (type.toString() === 'IDAT') idat = Buffer.concat([idat, data])
    offset += 12 + length
  }
  assert.equal(offset, onePixelPng.length)
  assert.deepEqual([width, height], [1, 1])
  assert.equal(inflateSync(idat).length, 5)
})
