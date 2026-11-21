/* LD_PRELOAD-Shim fuer hiby_player (iPod-Modus), Variante "Abgriff".
 * Der Player spielt normal auf /dev/snd/pcmC0D0p (echter Takt des Codecs). Wir merken uns
 * das fd, lesen bei HW_PARAMS Format/Rate/Kanaele mit und kopieren bei jedem WRITEI die
 * geschriebenen Frames nicht-blockierend in die FIFO /tmp/ipod.fifo (liest loopbridge.sh).
 * /tmp/loop_play enthaelt "FORMAT RATE KANAELE" fuer aplay. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdarg.h>
#include <errno.h>
#include <time.h>
#include <sys/ioctl.h>
#include <signal.h>

#define SRC "/dev/snd/pcmC0D0p"
#define FIFO "/tmp/ipod.fifo"
/* Grafik-DMA des Players (8 MB am Stueck). Mit grosser Musik-DB ist der Speicher beim
 * spaeten open() des Players zersplittert -> Bild friert. Wir oeffnen es im Konstruktor
 * (vor dem DB-Laden) und reichen das fd beim ersten open() des Players durch. */
#define HGL "/dev/sa_hgl_dma"
static int hglfd = -1;

static void *(*real_dlsym)(void *, const char *);
static int (*r_open)(const char *, int, ...);
static int (*r_open64)(const char *, int, ...);
static int (*r_close)(int);
static int (*r_ioctl)(int, unsigned long, ...);
static volatile int pcmfd = -1;
static int fifofd = -1;
static int framebytes = 0;
static unsigned long dropped = 0;

struct xferi { long result; void *buf; unsigned long frames; };

static void init_real(void) {
    if (!real_dlsym) real_dlsym = dlvsym(RTLD_NEXT, "dlsym", "GLIBC_2.0");
    if (!r_open) r_open = real_dlsym(RTLD_NEXT, "open");
    if (!r_open64) r_open64 = real_dlsym(RTLD_NEXT, "open64");
    if (!r_close) r_close = real_dlsym(RTLD_NEXT, "close");
    if (!r_ioctl) r_ioctl = real_dlsym(RTLD_NEXT, "ioctl");
}

static void logmsg(const char *m, const char *a, long b) {
    int fd; char buf[256]; int n;
    init_real();
    fd = r_open("/tmp/pcmshim.log", O_WRONLY | O_APPEND | O_CREAT, 0644);
    if (fd < 0) return;
    n = snprintf(buf, sizeof(buf), "%ld %s %s %ld\n", (long)time(NULL), m, a ? a : "-", b);
    if (write(fd, buf, n) < 0) {}
    r_close(fd);
}

static const char *fmtname(int idx) {
    switch (idx) {
    case 2: return "S16_LE"; case 6: return "S24_LE"; case 10: return "S32_LE";
    case 32: return "S24_3LE"; default: return NULL;
    }
}

static void write_info(const char *fmt, unsigned rate, unsigned ch) {
    int fd = r_open("/tmp/loop_play.tmp", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    char buf[64]; int n; struct timespec ts;
    if (fd < 0) return;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    n = snprintf(buf, sizeof(buf), "%s %u %u %ld\n", fmt, rate, ch, (long)ts.tv_nsec);
    if (write(fd, buf, n) < 0) {}
    r_close(fd);
    rename("/tmp/loop_play.tmp", "/tmp/loop_play");
}

static int is_audio(const char *p) {
    const char *e = strrchr(p, '.');
    if (!e) return 0;
    return !strcasecmp(e, ".opus") || !strcasecmp(e, ".flac") || !strcasecmp(e, ".mp3") ||
           !strcasecmp(e, ".m4a") || !strcasecmp(e, ".ogg") || !strcasecmp(e, ".wav") ||
           !strcasecmp(e, ".aac") || !strcasecmp(e, ".ape") || !strcasecmp(e, ".dsf");
}

static int do_open(int (*fn)(const char *, int, ...), const char *path, int flags, int mode) {
    int r;
    if (hglfd >= 0 && path && strcmp(path, HGL) == 0) {
        r = hglfd; hglfd = -1;
        logmsg("hgl-durchgereicht", path, flags);
        return r;
    }
    r = fn(path, flags, mode);
    if (r >= 0 && path && is_audio(path) && (flags & O_ACCMODE) == O_RDONLY) {
        /* aktuellen Titel fuer den iPod-Client merken */
        int fd = r_open("/tmp/now_playing.tmp", O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (fd >= 0) {
            if (write(fd, path, strlen(path)) < 0) {}
            r_close(fd);
            rename("/tmp/now_playing.tmp", "/tmp/now_playing");
        }
        logmsg("audio-open", path, r);
    }
    if (r >= 0 && path && strcmp(path, SRC) == 0 && access("/tmp/ipod_mode", F_OK) == 0) {
        pcmfd = r;
        logmsg("open-abgriff", path, r);
    }
    return r;
}

int open(const char *path, int flags, ...) {
    va_list ap; int mode;
    va_start(ap, flags); mode = va_arg(ap, int); va_end(ap);
    init_real();
    return do_open(r_open, path, flags, mode);
}

int open64(const char *path, int flags, ...) {
    va_list ap; int mode;
    va_start(ap, flags); mode = va_arg(ap, int); va_end(ap);
    init_real();
    return do_open(r_open64, path, flags, mode);
}

int close(int fd) {
    init_real();
    if (fd >= 0 && fd == pcmfd) {
        pcmfd = -1; framebytes = 0;
        if (fifofd >= 0) { r_close(fifofd); fifofd = -1; }
        unlink("/tmp/loop_play");
        logmsg("close", "pcm", dropped);
    }
    return r_close(fd);
}

static void tap(const void *buf, long frames) {
    long len; ssize_t w;
    if (framebytes <= 0 || frames <= 0 || !buf) return;
    if (fifofd < 0) {
        fifofd = r_open(FIFO, O_WRONLY | O_NONBLOCK, 0);   /* scheitert ohne Leser -> spaeter erneut */
        if (fifofd < 0) return;
    }
    len = frames * framebytes;
    w = write(fifofd, buf, len);
    if (w < 0) {
        if (errno == EPIPE) { r_close(fifofd); fifofd = -1; }
        dropped += len;
    } else if (w < len) {
        dropped += len - w;
    }
}

int ioctl(int fd, unsigned long req, ...) {
    va_list ap; void *arg; int r;
    va_start(ap, req); arg = va_arg(ap, void *); va_end(ap);
    init_real();
    r = r_ioctl(fd, req, arg);
    if (fd != pcmfd || r < 0 || _IOC_TYPE(req) != 'A' || !arg) return r;
    if (_IOC_NR(req) == 0x11) {          /* HW_PARAMS: Ergebnis auslesen */
        unsigned int *w = (unsigned int *)arg;
        unsigned int *iv = (unsigned int *)((char *)arg + 260);
        unsigned int fmtmask = w[9], bits = iv[0], ch = iv[6], rate = iv[9];
        int idx = 0; const char *fn;
        while (idx < 32 && !(fmtmask & (1u << idx))) idx++;
        fn = fmtname(idx);
        framebytes = (int)(bits / 8 * ch);
        if (fn) write_info(fn, rate, ch); else framebytes = 0;
        logmsg(fn ? fn : "fmt?", "hw_params", rate);
    } else if (_IOC_NR(req) == 0x50) {   /* WRITEI_FRAMES */
        struct xferi *x = arg;
        static time_t last_alive;
        time_t now = time(NULL);
        tap(x->buf, x->result);
        if (now != last_alive) {           /* Lebenszeichen: Player spielt gerade */
            int afd = r_open("/tmp/pcm_alive", O_WRONLY | O_CREAT | O_TRUNC, 0644);
            last_alive = now;
            if (afd >= 0) r_close(afd);
        }
    }
    return r;
}

__attribute__((constructor)) static void shim_init(void) {
    /* FIFO ohne Leser darf den Player nicht per SIGPIPE beenden */
    signal(SIGPIPE, SIG_IGN);
    init_real();
    extern char *program_invocation_short_name;   /* nur im Player selbst, nicht in Kindprozessen */
    if (strcmp(program_invocation_short_name, "hiby_player") == 0 &&
        access("/usr/data/hgl_prealloc_off", F_OK) != 0) {
        hglfd = r_open(HGL, O_RDWR, 0);
        logmsg("hgl-vorab", HGL, hglfd);
    }
}
