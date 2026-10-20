// bmp_dump: parse one BMP file from disk and print a one-line summary.
// Exists so the parser can be exercised (and its planted bugs verified)
// without a fuzzer: build with a sanitizer profile and run it on a file.
//
// Usage: bmp_dump <file.bmp>
// Exit:  0 = parsed, 1 = format error, 2 = usage / I/O error.
// A sanitizer report and abort is a finding, not an exit code.

#include <stdio.h>
#include <stdlib.h>

#include "bmp_parser.h"

int main(int argc, char **argv) {
  if (argc != 2) {
    fprintf(stderr, "usage: %s <file.bmp>\n", argv[0]);
    return 2;
  }
  FILE *f = fopen(argv[1], "rb");
  if (f == NULL) {
    perror("fopen");
    return 2;
  }
  if (fseek(f, 0, SEEK_END) != 0) {
    perror("fseek");
    fclose(f);
    return 2;
  }
  long len = ftell(f);
  if (len < 0 || fseek(f, 0, SEEK_SET) != 0) {
    perror("ftell/fseek");
    fclose(f);
    return 2;
  }
  // Exact-size heap buffer on purpose: out-of-bounds reads past the
  // file image must land in a redzone a sanitizer can see.
  uint8_t *buf = (uint8_t *)malloc(len > 0 ? (size_t)len : 1);
  if (buf == NULL) {
    fclose(f);
    return 2;
  }
  if (len > 0 && fread(buf, 1, (size_t)len, f) != (size_t)len) {
    fprintf(stderr, "short read\n");
    free(buf);
    fclose(f);
    return 2;
  }
  fclose(f);

  BmpImage img;
  int rc = bmp_parse(buf, (size_t)len, &img);
  if (rc == 0) {
    printf("OK width=%d height=%d bpp=%u stride=%u palette_first=%08x "
           "palette_last=%08x\n",
           img.width, img.height, (unsigned)img.bpp, img.stride,
           img.palette_first, img.palette_last);
    bmp_image_free(&img);
  } else {
    printf("parse error (%d)\n", rc);
  }
  free(buf);
  return rc == 0 ? 0 : 1;
}
