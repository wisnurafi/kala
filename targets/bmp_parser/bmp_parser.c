#include "bmp_parser.h"

#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#define BMP_MIN_SIZE 54u // 14-byte file header + 40-byte info header

static uint16_t get_u16le(const uint8_t *p) {
  return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t get_u32le(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}

static int32_t get_i32le(const uint8_t *p) {
  uint32_t u = get_u32le(p);
  int32_t v;
  memcpy(&v, &u, sizeof(v));
  return v;
}

// Reads the color palette of an 8bpp image into the image record.
// Palette entries sit immediately before the pixel data, so the first
// entry is located by walking back from bfOffBits.
static void parse_palette(const uint8_t *data, uint32_t data_offset,
                          uint32_t colors_used, BmpImage *img) {
  const uint8_t *src = data + data_offset - (size_t)colors_used * 4u;
  uint32_t palette[256];
  for (uint32_t i = 0; i < colors_used; i++) {
    palette[i] = get_u32le(src + (size_t)i * 4u);
  }
  img->palette_first = palette[0];
  img->palette_last = palette[colors_used - 1];
}

// Minimal RLE8 decoder used for BI_RLE8 files. A valid stream ends
// with the end-of-bitmap marker (0x00, 0x01); anything else is rejected
// so the caller can fall back to a raw copy. On success *out owns a
// freshly allocated buffer holding the stream bytes.
static int rle8_decompress(const uint8_t *src, size_t avail, uint8_t **out) {
  if (avail < 4) {
    return -1;
  }
  if (src[avail - 2] != 0x00 || src[avail - 1] != 0x01) {
    return -1;
  }
  uint8_t *buf = (uint8_t *)malloc(avail);
  if (buf == NULL) {
    return -1;
  }
  memcpy(buf, src, avail);
  *out = buf;
  return 0;
}

// Copies `rows` rows of `stride` bytes from the pixel array into the
// freshly allocated pixel buffer, flipping row order for bottom-up
// files.
static void copy_rows(const uint8_t *data, uint32_t data_offset,
                      uint32_t stride, uint32_t rows, bool top_down,
                      uint8_t *pixels) {
  const uint8_t *src = data + data_offset;
  for (uint32_t i = 0; i < rows; i++) {
    uint32_t dest_row = top_down ? i : (rows - 1u - i);
    memcpy(pixels + (size_t)dest_row * stride, src + (size_t)i * stride,
           stride);
  }
}

int bmp_parse(const uint8_t *data, size_t size, BmpImage *img) {
  if (data == NULL || img == NULL || size < BMP_MIN_SIZE) {
    return -1;
  }
  memset(img, 0, sizeof(*img));

  if (data[0] != 'B' || data[1] != 'M') {
    return -1;
  }
  uint32_t data_offset = get_u32le(data + 10);
  uint32_t dib_size = get_u32le(data + 14);
  if (dib_size < 40) {
    return -1;
  }
  int32_t width = get_i32le(data + 18);
  int32_t height = get_i32le(data + 22);
  uint16_t planes = get_u16le(data + 26);
  uint16_t bpp = get_u16le(data + 28);
  uint32_t compression = get_u32le(data + 30);
  uint32_t colors_used = get_u32le(data + 46);
  if (planes != 1 || width <= 0 || height == 0) {
    return -1;
  }
  if (compression != 0 && compression != 1) {
    return -1; // only BI_RGB and BI_RLE8 are handled
  }
  uint32_t bytes_per_pixel;
  switch (bpp) {
    case 8: bytes_per_pixel = 1; break;
    case 16: bytes_per_pixel = 2; break;
    case 24: bytes_per_pixel = 3; break;
    case 32: bytes_per_pixel = 4; break;
    default: return -1;
  }
  uint32_t rows = (uint32_t)(height < 0 ? -(int64_t)height : (int64_t)height);
  uint32_t stride =
      (uint32_t)(((uint64_t)(uint32_t)width * bytes_per_pixel + 3u) & ~3ull);

  if (bpp == 8) {
    parse_palette(data, data_offset, colors_used ? colors_used : 256u, img);
  }

  uint32_t alloc_size = stride * rows;
  uint8_t *pixels = (uint8_t *)malloc(alloc_size);
  if (pixels == NULL) {
    return -1;
  }
  img->width = width;
  img->height = height;
  img->bpp = bpp;
  img->stride = stride;
  img->pixels = pixels;

  bool decoded = false;
  if (compression == 1) { // BI_RLE8: decode, fall back to raw copy
    size_t avail = data_offset < size ? size - data_offset : 0;
    const uint8_t *src = data + data_offset;
    uint8_t *decoded_buf = NULL;
    free(pixels);
    if (rle8_decompress(src, avail, &decoded_buf) == 0) {
      img->pixels = pixels = decoded_buf;
      decoded = true;
    }
  }
  if (!decoded) {
    copy_rows(data, data_offset, stride, rows, height < 0, pixels);
  }
  return 0;
}

void bmp_image_free(BmpImage *img) {
  if (img == NULL) {
    return;
  }
  free(img->pixels);
  img->pixels = NULL;
}
