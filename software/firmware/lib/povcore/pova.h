// pova.h - the .pova animation container, mirror of software/povgen/povanim.py (Animation.to_bytes / from_bytes).
// Layout (little-endian): "POVA" u8 ver=1, u8 flags(bit0 loop, bit1 rle), u8 rows=42, u8 cols=96, u16 nframes,
// u16 fps_x10, u8 npal, u8 reserved, u16 meta_len, meta JSON, palette npal*RGB, frames [u8 hold, u8 res, u16 len, data],
// u32 crc32 (zlib / IEEE) over everything before it. RLE data = (run u8, index u8) pairs, row-major, 4032 pixels.
// Host-tested against the dog animation written by povanim.py (test/test_pova).
#pragma once
#include "pov_compat.h"
#include "povframe.h"

#define POVA_MAX_PAL POV_MAX_PAL
#define POVA_FRAME_PIXELS POV_FRAME_PIXELS
#define POVA_MAX_FRAMES 256
#define POVA_MAX_FILE 65536   // whole file stays in RAM while it plays; the uploader refuses bigger files (413)

struct PovaHeader {
  char magic[4];
  uint8_t version, flags, rows, cols;
  uint16_t nframes, fps_x10;
  uint8_t npal, reserved;
  uint16_t meta_len;
} __attribute__((packed));

// A loaded animation: palette (sRGB), frame table pointing into the file image kept in RAM, metadata strings
struct PovaAnim {
  const uint8_t* file = nullptr;   // whole file in RAM (malloc'd by the loader, freed when replaced)
  size_t size = 0;
  uint16_t nframes = 0, fps_x10 = 150;
  bool loop = true, rle = true;
  uint8_t npal = 0;
  uint8_t pal_rgb[POVA_MAX_PAL][3];
  const uint8_t* frame_data[POVA_MAX_FRAMES];
  uint16_t frame_len[POVA_MAX_FRAMES];
  uint8_t frame_hold[POVA_MAX_FRAMES];
  char name[32];
  char scope[8];                   // "home" | "public" from the meta JSON (string search; no JSON parser needed)
};

// zlib-compatible CRC-32 (bitwise; a 64 KB file takes a few ms, once per load)
static inline uint32_t pova_crc32(const uint8_t* p, size_t n, uint32_t crc = 0) {
  crc = ~crc;
  for (size_t i = 0; i < n; i++) {
    crc ^= p[i];
    for (int b = 0; b < 8; b++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}

static inline uint16_t pova_u16(const uint8_t* p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static inline uint32_t pova_u32(const uint8_t* p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24); }

static inline void pova_meta_str(const uint8_t* meta, size_t meta_len, const char* key, char* out, size_t outn) {
  out[0] = 0;
  size_t kl = strlen(key);
  const uint8_t* s = pov::memmem_(meta, meta_len, key, kl);
  if (!s) return;
  s += kl;
  size_t avail = (size_t)(meta + meta_len - s);
  size_t k = 0;
  while (k < outn - 1 && k < avail && s[k] && s[k] != '"') { out[k] = (char)s[k]; k++; }
  out[k] = 0;
}

// Parse a file image. `check_crc` = true for uploads; the test corpus is checked both ways.
static inline bool pova_parse(PovaAnim& a, const uint8_t* buf, size_t n, bool check_crc = true) {
  if (n < sizeof(PovaHeader) + 4 || memcmp(buf, "POVA", 4) != 0) return false;
  if (check_crc && pova_crc32(buf, n - 4) != pova_u32(buf + n - 4)) return false;
  const PovaHeader* h = (const PovaHeader*)buf;
  uint16_t nframes = pova_u16((const uint8_t*)&h->nframes), fps_x10 = pova_u16((const uint8_t*)&h->fps_x10);
  uint16_t meta_len = pova_u16((const uint8_t*)&h->meta_len);
  if (h->version != 1 || h->rows != POV_ROWS || h->cols != POV_COLS || h->npal > POVA_MAX_PAL || nframes > POVA_MAX_FRAMES)
    return false;
  size_t p = sizeof(PovaHeader);
  if (p + meta_len + 3u * h->npal + 4 > n) return false;
  const uint8_t* meta = buf + p;
  pova_meta_str(meta, meta_len, "\"scope\":\"", a.scope, sizeof a.scope);
  pova_meta_str(meta, meta_len, "\"name\":\"", a.name, sizeof a.name);
  p += meta_len;
  a.npal = h->npal;
  memset(a.pal_rgb, 0, sizeof a.pal_rgb);
  memcpy(a.pal_rgb, buf + p, 3u * h->npal);
  p += 3u * h->npal;
  a.nframes = nframes;
  a.fps_x10 = fps_x10 ? fps_x10 : 150;
  a.loop = (h->flags & 1) != 0;
  a.rle = (h->flags & 2) != 0;
  for (uint16_t i = 0; i < nframes; i++) {
    if (p + 4 > n - 4) return false;
    a.frame_hold[i] = buf[p] ? buf[p] : 1;
    uint16_t len = pova_u16(buf + p + 2);
    p += 4;
    if (p + len > n - 4) return false;
    if (!a.rle && len != POVA_FRAME_PIXELS) return false;
    a.frame_data[i] = buf + p;
    a.frame_len[i] = len;
    p += len;
  }
  if (p != n - 4) return false;      // trailing bytes other than the CRC
  a.file = buf;
  a.size = n;
  return true;
}

// Decode frame i into out[4032]. Returns false if the RLE does not fill the frame exactly.
static inline bool pova_decode(const PovaAnim& a, uint16_t i, uint8_t* out) {
  if (i >= a.nframes) return false;
  const uint8_t* d = a.frame_data[i];
  if (!a.rle) { memcpy(out, d, POVA_FRAME_PIXELS); return true; }
  size_t pos = 0;
  for (uint16_t k = 0; k + 1 < a.frame_len[i]; k += 2) {
    uint8_t run = d[k], v = d[k + 1];
    if (pos + run > POVA_FRAME_PIXELS) return false;
    memset(out + pos, v, run);
    pos += run;
  }
  return pos == POVA_FRAME_PIXELS;
}

// ---------------------------------------------------------------------------------------------------------------------
// Streaming validator (Wi-Fi control review 2026-11-14, docs/2026-11-14-wifi-control-review.md). Checks a .pova file fed
// in pieces of any size, as the upload arrives or as it is read back from LittleFS, with ~60 bytes of state and NO
// file-sized buffer. The old upload check malloc'd the whole file (up to 64 KB) to parse it; on a fragmented heap that
// malloc failed, a valid file was answered "bad file" and the reject path crashed the board (2026-11-13/14).
// Accepts exactly what pova_parse(check_crc=true) accepts, and also requires: at least one frame, RLE runs that fill
// every frame exactly (even length), and palette indices below npal (the column engine indexes a 32-entry palette).
struct PovaCheck {
  enum : uint8_t { S_HDR, S_META, S_PAL, S_FHDR, S_FDATA, S_CRC, S_DONE, S_ERR };
  uint8_t st;
  uint8_t hdr[16], hn;        // header bytes collected so far
  uint8_t fh[4], fhn;         // current frame header
  uint8_t crcb[4], crcn;      // trailing CRC bytes
  uint8_t npal;
  bool rle, run_pending;      // RLE: a run byte was read, its index byte is next
  uint8_t run;
  uint16_t nframes, fi, flen, fdone;
  uint32_t need;              // bytes left in the current META / PAL section
  uint32_t total;             // bytes fed so far
  uint32_t crc;               // running CRC-32 over everything before the CRC field
  uint32_t px;                // pixels decoded in the current frame
  const char* err;            // reason once st == S_ERR (static string)
};

static inline void pova_check_begin(PovaCheck& c) {
  memset(&c, 0, sizeof c);
  c.st = PovaCheck::S_HDR;
}

static inline bool pova_check_fail(PovaCheck& c, const char* why) {
  c.st = PovaCheck::S_ERR;
  c.err = why;
  return false;
}

// Feed the next piece. Returns false as soon as the file is known to be bad (then c.err says why).
static inline bool pova_check_feed(PovaCheck& c, const uint8_t* p, size_t n) {
  if (c.st == PovaCheck::S_ERR) return false;
  if ((uint64_t)c.total + n > POVA_MAX_FILE) return pova_check_fail(c, "too big (max 65536 B)");
  c.total += (uint32_t)n;
  while (n) {
    switch (c.st) {
      case PovaCheck::S_HDR: {
        size_t k = std::min(n, (size_t)(16 - c.hn));
        memcpy(c.hdr + c.hn, p, k);
        c.crc = pova_crc32(p, k, c.crc);
        c.hn = (uint8_t)(c.hn + k); p += k; n -= k;
        if (c.hn < 16) break;
        if (memcmp(c.hdr, "POVA", 4) != 0) return pova_check_fail(c, "not a .pova file (magic)");
        c.nframes = pova_u16(c.hdr + 8);
        c.npal = c.hdr[12];
        c.rle = (c.hdr[5] & 2) != 0;
        if (c.hdr[4] != 1 || c.hdr[6] != POV_ROWS || c.hdr[7] != POV_COLS || c.npal > POVA_MAX_PAL || c.npal == 0 ||
            c.nframes == 0 || c.nframes > POVA_MAX_FRAMES)
          return pova_check_fail(c, "bad header (version, size, palette or frame count)");
        c.need = pova_u16(c.hdr + 14);
        c.st = c.need ? PovaCheck::S_META : PovaCheck::S_PAL;
        if (c.st == PovaCheck::S_PAL) c.need = 3u * c.npal;
        break;
      }
      case PovaCheck::S_META:
      case PovaCheck::S_PAL: {
        size_t k = std::min(n, (size_t)c.need);
        c.crc = pova_crc32(p, k, c.crc);
        c.need -= (uint32_t)k; p += k; n -= k;
        if (c.need) break;
        if (c.st == PovaCheck::S_META) { c.st = PovaCheck::S_PAL; c.need = 3u * c.npal; }
        else c.st = PovaCheck::S_FHDR;
        break;
      }
      case PovaCheck::S_FHDR: {
        size_t k = std::min(n, (size_t)(4 - c.fhn));
        memcpy(c.fh + c.fhn, p, k);
        c.crc = pova_crc32(p, k, c.crc);
        c.fhn = (uint8_t)(c.fhn + k); p += k; n -= k;
        if (c.fhn < 4) break;
        c.fhn = 0;
        c.flen = pova_u16(c.fh + 2);
        if (!c.rle && c.flen != POVA_FRAME_PIXELS) return pova_check_fail(c, "bad frame length (raw frame)");
        if (c.rle && (c.flen & 1)) return pova_check_fail(c, "bad frame length (odd RLE)");
        c.fdone = 0; c.px = 0; c.run_pending = false;
        c.st = PovaCheck::S_FDATA;
        if (c.flen == 0) return pova_check_fail(c, "empty frame");
        break;
      }
      case PovaCheck::S_FDATA: {
        size_t k = std::min(n, (size_t)(c.flen - c.fdone));
        c.crc = pova_crc32(p, k, c.crc);
        for (size_t i = 0; i < k; i++) {
          uint8_t b = p[i];
          if (!c.rle) {
            if (b >= c.npal) return pova_check_fail(c, "palette index out of range");
          } else if (!c.run_pending) {
            c.run = b; c.run_pending = true;
          } else {
            c.run_pending = false;
            if (b >= c.npal && c.run) return pova_check_fail(c, "palette index out of range");
            c.px += c.run;
            if (c.px > POVA_FRAME_PIXELS) return pova_check_fail(c, "bad RLE (frame overflows 4032 px)");
          }
        }
        c.fdone = (uint16_t)(c.fdone + k); p += k; n -= k;
        if (c.fdone < c.flen) break;
        if (c.rle && c.px != POVA_FRAME_PIXELS) return pova_check_fail(c, "bad RLE (frame is not 4032 px)");
        c.fi++;
        c.st = c.fi < c.nframes ? PovaCheck::S_FHDR : PovaCheck::S_CRC;
        break;
      }
      case PovaCheck::S_CRC: {
        size_t k = std::min(n, (size_t)(4 - c.crcn));
        memcpy(c.crcb + c.crcn, p, k);
        c.crcn = (uint8_t)(c.crcn + k); p += k; n -= k;
        if (c.crcn < 4) break;
        if (pova_u32(c.crcb) != c.crc) return pova_check_fail(c, "CRC mismatch (file damaged in transfer)");
        c.st = PovaCheck::S_DONE;
        break;
      }
      case PovaCheck::S_DONE:
        return pova_check_fail(c, "trailing bytes after the CRC");
      default:
        return false;
    }
  }
  return true;
}

// After the last piece: true = a complete, valid file. Otherwise c.err says why ("truncated" if it simply ended early).
static inline bool pova_check_end(PovaCheck& c) {
  if (c.st == PovaCheck::S_DONE) return true;
  if (c.st != PovaCheck::S_ERR) pova_check_fail(c, "truncated (file ended early)");
  return false;
}
