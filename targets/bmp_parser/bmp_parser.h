#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Minimal BMP parser (BITMAPINFOHEADER / V4 / V5 layouts, uncompressed
// and RLE8). Written as a calibration target for the Kala pipeline:
// it is functional for well-formed files, and it is the practice
// target (see PLANTED_BUGS.md, which is the answer key and must not
// be consulted during triage validation).
typedef struct {
  int32_t width;
  int32_t height; // negative for top-down files, as stored in the header
  uint16_t bpp;
  uint32_t stride; // bytes per row, padded to a 4-byte boundary
  uint8_t *pixels; // owned; stride * abs(height) bytes
  uint32_t palette_first;
  uint32_t palette_last;
} BmpImage;

// Parses a BMP held in memory. Returns 0 on success and fills `img`
// (caller releases it with bmp_image_free), or a negative value on a
// format error. The parser trusts header fields the way many small
// loaders do; hostile input is the fuzzer's job to survive, not the
// caller's.
int bmp_parse(const uint8_t *data, size_t size, BmpImage *img);

void bmp_image_free(BmpImage *img);

#ifdef __cplusplus
}
#endif
