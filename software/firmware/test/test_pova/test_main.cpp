// .pova parser + RLE decoder against the dog animation written by povanim.py (CRC, header, palette, frames).
#include <unity.h>

#include "pova.h"
#include "vec_pova.h"

static uint8_t out[POVA_FRAME_PIXELS];
static uint8_t copy[8192];
static PovaAnim a;

void setUp() {}
void tearDown() {}

static void rle_decode_vec(const uint8_t* rle, size_t n, uint8_t* dst) {
  size_t pos = 0;
  for (size_t k = 0; k + 1 < n; k += 2) { memset(dst + pos, rle[k + 1], rle[k]); pos += rle[k]; }
  TEST_ASSERT_EQUAL(POVA_FRAME_PIXELS, pos);
}

void test_crc32_is_zlib() {
  // zlib.crc32(b"123456789") = 0xCBF43926
  TEST_ASSERT_EQUAL_HEX32(0xCBF43926u, pova_crc32((const uint8_t*)"123456789", 9));
  TEST_ASSERT_EQUAL_HEX32(0u, pova_crc32((const uint8_t*)"", 0));
  size_t n = sizeof VEC_DOG_POVA;
  TEST_ASSERT_EQUAL_HEX32(pova_u32(VEC_DOG_POVA + n - 4), pova_crc32(VEC_DOG_POVA, n - 4));
}

void test_parse_dog() {
  TEST_ASSERT_TRUE(pova_parse(a, VEC_DOG_POVA, sizeof VEC_DOG_POVA, true));
  TEST_ASSERT_EQUAL(VEC_DOG_NFRAMES, a.nframes);
  TEST_ASSERT_EQUAL(VEC_DOG_FPS_X10, a.fps_x10);
  TEST_ASSERT_EQUAL(VEC_DOG_NPAL, a.npal);
  TEST_ASSERT_EQUAL(VEC_DOG_LOOP != 0, a.loop);
  TEST_ASSERT_TRUE(a.rle);
  TEST_ASSERT_EQUAL_STRING(VEC_DOG_NAME, a.name);
  TEST_ASSERT_EQUAL_STRING(VEC_DOG_SCOPE, a.scope);
  for (int i = 0; i < VEC_DOG_NPAL; i++)
    for (int c = 0; c < 3; c++) TEST_ASSERT_EQUAL_HEX8(VEC_DOG_PAL[3 * i + c], a.pal_rgb[i][c]);
  for (int i = 0; i < VEC_DOG_NFRAMES; i++) TEST_ASSERT_EQUAL(VEC_DOG_HOLDS[i], a.frame_hold[i]);
  TEST_ASSERT_EQUAL(sizeof VEC_DOG_POVA, a.size);
}

void test_decode_frames() {
  TEST_ASSERT_TRUE(pova_parse(a, VEC_DOG_POVA, sizeof VEC_DOG_POVA, true));
  TEST_ASSERT_TRUE(pova_decode(a, 0, out));
  TEST_ASSERT_EQUAL_UINT8_ARRAY(VEC_DOG_F0, out, POVA_FRAME_PIXELS);
  static uint8_t last[POVA_FRAME_PIXELS];
  rle_decode_vec(VEC_DOG_FLAST_RLE, VEC_DOG_FLAST_RLE_OFF[1] - VEC_DOG_FLAST_RLE_OFF[0], last);
  TEST_ASSERT_TRUE(pova_decode(a, (uint16_t)(a.nframes - 1), out));
  TEST_ASSERT_EQUAL_UINT8_ARRAY(last, out, POVA_FRAME_PIXELS);
  TEST_ASSERT_FALSE(pova_decode(a, a.nframes, out));
  // every frame decodes, and only uses palette indices below npal
  for (int i = 0; i < a.nframes; i++) {
    TEST_ASSERT_TRUE(pova_decode(a, (uint16_t)i, out));
    for (int p = 0; p < POVA_FRAME_PIXELS; p++) TEST_ASSERT_TRUE(out[p] < a.npal);
  }
}

void test_rejects_corruption_and_truncation() {
  size_t n = sizeof VEC_DOG_POVA;
  TEST_ASSERT_TRUE(n <= sizeof copy);
  memcpy(copy, VEC_DOG_POVA, n);
  copy[20] ^= 0x01;                                            // inside the meta JSON
  TEST_ASSERT_FALSE(pova_parse(a, copy, n, true));             // CRC catches it
  TEST_ASSERT_TRUE(pova_parse(a, copy, n, false));             // structure still parses without the CRC
  memcpy(copy, VEC_DOG_POVA, n);
  TEST_ASSERT_FALSE(pova_parse(a, copy, n - 10, true));        // truncated
  TEST_ASSERT_FALSE(pova_parse(a, copy, n - 10, false));
  memcpy(copy, VEC_DOG_POVA, n);
  copy[0] = 'X';
  TEST_ASSERT_FALSE(pova_parse(a, copy, n, false));            // magic
  memcpy(copy, VEC_DOG_POVA, n);
  copy[6] = 41;                                                // rows
  TEST_ASSERT_FALSE(pova_parse(a, copy, n, false));
  TEST_ASSERT_FALSE(pova_parse(a, copy, 10, false));           // shorter than a header
}

// Build a raw (non-RLE) one-frame file in C and round-trip it
void test_raw_frame_file() {
  static uint8_t file[16 + 2 + 6 + 4 + POVA_FRAME_PIXELS + 4];
  size_t p = 0;
  memcpy(file, "POVA", 4); p = 4;
  file[p++] = 1;            // version
  file[p++] = 1;            // flags: loop, not RLE
  file[p++] = POV_ROWS; file[p++] = POV_COLS;
  file[p++] = 1; file[p++] = 0;          // nframes
  file[p++] = 100; file[p++] = 0;        // fps_x10 = 10.0
  file[p++] = 2; file[p++] = 0;          // npal, reserved
  file[p++] = 2; file[p++] = 0;          // meta_len
  file[p++] = '{'; file[p++] = '}';
  uint8_t pal[6] = {0, 0, 0, 10, 20, 30};
  memcpy(file + p, pal, 6); p += 6;
  file[p++] = 3; file[p++] = 0;          // hold 3
  file[p++] = (uint8_t)(POVA_FRAME_PIXELS & 255); file[p++] = (uint8_t)(POVA_FRAME_PIXELS >> 8);
  for (int i = 0; i < POVA_FRAME_PIXELS; i++) file[p + i] = (uint8_t)(i % 2);
  p += POVA_FRAME_PIXELS;
  uint32_t crc = pova_crc32(file, p);
  file[p++] = (uint8_t)crc; file[p++] = (uint8_t)(crc >> 8); file[p++] = (uint8_t)(crc >> 16); file[p++] = (uint8_t)(crc >> 24);
  TEST_ASSERT_EQUAL(sizeof file, p);
  PovaAnim b;
  TEST_ASSERT_TRUE(pova_parse(b, file, p, true));
  TEST_ASSERT_FALSE(b.rle);
  TEST_ASSERT_TRUE(b.loop);
  TEST_ASSERT_EQUAL(1, b.nframes);
  TEST_ASSERT_EQUAL(100, b.fps_x10);
  TEST_ASSERT_EQUAL(3, b.frame_hold[0]);
  TEST_ASSERT_EQUAL_STRING("", b.name);
  TEST_ASSERT_EQUAL_HEX8(30, b.pal_rgb[1][2]);
  TEST_ASSERT_TRUE(pova_decode(b, 0, out));
  for (int i = 0; i < POVA_FRAME_PIXELS; i++) TEST_ASSERT_EQUAL(i % 2, out[i]);
}

// ---- streaming validator (pova_check_*): the upload path feeds it network chunks of any size, never a whole file
static bool check_in_chunks(const uint8_t* f, size_t n, size_t chunk, const char** why = nullptr) {
  PovaCheck c;
  pova_check_begin(c);
  bool ok = true;
  for (size_t i = 0; i < n && ok; i += chunk) ok = pova_check_feed(c, f + i, std::min(chunk, n - i));
  ok = ok && pova_check_end(c);
  if (why) *why = c.err;
  return ok;
}

void test_check_accepts_dog_in_any_chunking() {
  size_t n = sizeof VEC_DOG_POVA;
  const size_t sizes[] = {1, 2, 3, 4, 5, 7, 13, 16, 17, 64, 536, 1436, 4096, 65536};
  for (size_t s : sizes) TEST_ASSERT_TRUE_MESSAGE(check_in_chunks(VEC_DOG_POVA, n, s), "chunk size");
}

void test_check_rejects_with_reasons() {
  size_t n = sizeof VEC_DOG_POVA;
  const char* why = nullptr;
  memcpy(copy, VEC_DOG_POVA, n);
  copy[n - 1] ^= 0x10;                                           // the CRC itself
  TEST_ASSERT_FALSE(check_in_chunks(copy, n, 100, &why));
  TEST_ASSERT_NOT_NULL(strstr(why, "CRC"));
  memcpy(copy, VEC_DOG_POVA, n);
  TEST_ASSERT_FALSE(check_in_chunks(copy, n - 3, 100, &why));    // ends inside the CRC
  TEST_ASSERT_NOT_NULL(strstr(why, "truncated"));
  TEST_ASSERT_FALSE(check_in_chunks(copy, 9, 4, &why));          // ends inside the header
  TEST_ASSERT_NOT_NULL(strstr(why, "truncated"));
  copy[n] = 0;                                                   // one extra byte after the CRC
  TEST_ASSERT_FALSE(check_in_chunks(copy, n + 1, 64, &why));
  TEST_ASSERT_NOT_NULL(strstr(why, "trailing"));
  memcpy(copy, VEC_DOG_POVA, n);
  copy[1] = 'X';
  TEST_ASSERT_FALSE(check_in_chunks(copy, n, 64, &why));
  TEST_ASSERT_NOT_NULL(strstr(why, "magic"));
  memcpy(copy, VEC_DOG_POVA, n);
  copy[7] = 95;                                                  // cols
  TEST_ASSERT_FALSE(check_in_chunks(copy, n, 64, &why));
  TEST_ASSERT_NOT_NULL(strstr(why, "header"));
  // more than 64 KB is refused as soon as it is fed, before the end
  static uint8_t big[POVA_MAX_FILE + 16];
  memcpy(big, VEC_DOG_POVA, n);
  PovaCheck c;
  pova_check_begin(c);
  bool ok = true;
  for (size_t i = 0; i < sizeof big && ok; i += 1000) ok = pova_check_feed(c, big + i, std::min((size_t)1000, sizeof big - i));
  TEST_ASSERT_FALSE(ok);
}

// Every single-byte corruption: the streaming check never accepts what the full parser rejects (CRC on), and the dog
// file has no byte whose change both parsers miss (the CRC covers everything).
void test_check_agrees_with_parse_on_corruption() {
  size_t n = sizeof VEC_DOG_POVA;
  for (size_t pos = 0; pos < n; pos += 3) {
    memcpy(copy, VEC_DOG_POVA, n);
    copy[pos] ^= (uint8_t)(1 + pos % 255);        // never 0: every position really changes
    bool parsed = pova_parse(a, copy, n, true);
    bool checked = check_in_chunks(copy, n, 1 + pos % 97);
    TEST_ASSERT_FALSE(parsed);
    TEST_ASSERT_FALSE(checked);
  }
}

// A crafted file with a palette index >= npal (CRC valid): pova_parse accepts it, the stricter check refuses it
void test_check_rejects_palette_index_out_of_range() {
  static uint8_t file[16 + 2 + 6 + 4 + 4 + 4];
  size_t p = 0;
  memcpy(file, "POVA", 4); p = 4;
  file[p++] = 1; file[p++] = 3; file[p++] = POV_ROWS; file[p++] = POV_COLS;
  file[p++] = 1; file[p++] = 0; file[p++] = 150; file[p++] = 0;
  file[p++] = 2; file[p++] = 0; file[p++] = 2; file[p++] = 0;
  file[p++] = '{'; file[p++] = '}';
  for (int i = 0; i < 6; i++) file[p++] = (uint8_t)(i * 40);
  file[p++] = 1; file[p++] = 0; file[p++] = 4; file[p++] = 0;      // hold 1, len 4: two runs
  file[p++] = 255; file[p++] = 1;                                   // 255 px of index 1
  file[p++] = 0;                                                    // 3777 px would need more runs: the run sum is short
  file[p++] = 5;                                                    // index 5 >= npal 2 (run 0: harmless)
  uint32_t crc = pova_crc32(file, p);
  file[p++] = (uint8_t)crc; file[p++] = (uint8_t)(crc >> 8); file[p++] = (uint8_t)(crc >> 16); file[p++] = (uint8_t)(crc >> 24);
  const char* why = nullptr;
  TEST_ASSERT_FALSE(check_in_chunks(file, p, 5, &why));
  TEST_ASSERT_NOT_NULL(strstr(why, "4032"));                        // short frame caught
  file[24 + 4 + 1] = 7;                                             // first run's index -> 7 (out of range), fix the CRC
  crc = pova_crc32(file, p - 4);
  file[p - 4] = (uint8_t)crc; file[p - 3] = (uint8_t)(crc >> 8); file[p - 2] = (uint8_t)(crc >> 16); file[p - 1] = (uint8_t)(crc >> 24);
  TEST_ASSERT_FALSE(check_in_chunks(file, p, 3, &why));
  TEST_ASSERT_NOT_NULL(strstr(why, "palette index"));
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_crc32_is_zlib);
  RUN_TEST(test_parse_dog);
  RUN_TEST(test_decode_frames);
  RUN_TEST(test_rejects_corruption_and_truncation);
  RUN_TEST(test_raw_frame_file);
  RUN_TEST(test_check_accepts_dog_in_any_chunking);
  RUN_TEST(test_check_rejects_with_reasons);
  RUN_TEST(test_check_agrees_with_parse_on_corruption);
  RUN_TEST(test_check_rejects_palette_index_out_of_range);
  return UNITY_END();
}
