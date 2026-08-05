/*
 * StickCPU firmware — StickOS with universal .app runner + ADAPT.
 * Host contract: USB VBUS only.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#define MAX_STACK 256
#define MAX_CALL  64
#define VAR_SLOTS 256
#define MAX_FILES 48
#define MAX_STRS  96
#define MAX_NAME  64
#define MAX_CODE  8192
#define MAX_FILEDATA 512
#define MAX_FRAMES 8
#define MAX_APPQ 48

#include "rom_image.h"

typedef struct {
    char name[MAX_NAME];
    uint8_t data[MAX_FILEDATA];
    uint16_t len;
} StickFile;

typedef struct {
    uint8_t version;
    uint8_t mem_kb;
    uint16_t entry;
    uint8_t code[MAX_CODE];
    uint16_t code_len;
    char *strings[MAX_STRS];
    uint16_t str_count;
    StickFile files[MAX_FILES];
    uint16_t file_count;
    char banner[64];
} Image;

typedef struct {
    uint8_t code[MAX_CODE];
    uint16_t code_len;
    char *strings[MAX_STRS];
    uint16_t str_count;
    uint16_t pc;
    int32_t vars[VAR_SLOTS];
    uint16_t call[MAX_CALL];
    int csp;
    int32_t stack[MAX_STACK];
    int sp;
    int owns_strings;
} Frame;

typedef struct {
    Image img;
    /* active program (kernel or guest app) */
    uint8_t *code;
    uint16_t code_len;
    char **strings;
    uint16_t str_count;
    int32_t stack[MAX_STACK];
    int sp;
    uint16_t call[MAX_CALL];
    int csp;
    int32_t vars[VAR_SLOTS];
    uint16_t pc;
    uint32_t ticks;
    int halted;
    char halt_reason[64];
    int adapt_mode;
    Frame frames[MAX_FRAMES];
    int fp;
    char appq[MAX_APPQ][MAX_NAME];
    int appq_n;
    int guest_owns_strings;
} CPU;

static void uart_line(const char *s) {
    fputs(s, stdout);
    fputc('\n', stdout);
    fflush(stdout);
}

static void die_trap(CPU *cpu, const char *msg) {
    snprintf(cpu->halt_reason, sizeof(cpu->halt_reason), "trap: %s", msg);
    cpu->halted = 1;
}

static void push(CPU *cpu, int32_t v) {
    if (cpu->sp >= MAX_STACK) { die_trap(cpu, "stack overflow"); return; }
    cpu->stack[cpu->sp++] = v;
}

static int32_t pop(CPU *cpu) {
    if (cpu->sp <= 0) { die_trap(cpu, "stack underflow"); return 0; }
    return cpu->stack[--cpu->sp];
}

static uint16_t rd_u16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static int16_t rd_i16(const uint8_t *p) { return (int16_t)rd_u16(p); }

static int parse_image(Image *img, const uint8_t *blob, size_t len) {
    size_t off = 0;
    if (len < 15) return -1;
    if (blob[0] != 'S' || blob[1] != 'T' || blob[2] != 'K' || blob[3] != '1') return -1;
    img->version = blob[4];
    img->mem_kb = blob[5];
    img->entry = rd_u16(blob + 6);
    img->code_len = rd_u16(blob + 8);
    img->str_count = rd_u16(blob + 10);
    img->file_count = rd_u16(blob + 12);
    uint8_t blen = blob[14];
    off = 15;
    if (off + blen > len) return -1;
    if (blen >= sizeof(img->banner)) blen = sizeof(img->banner) - 1;
    memcpy(img->banner, blob + off, blen);
    img->banner[blen] = 0;
    off += blob[14];
    if (off + img->code_len > len || img->code_len > MAX_CODE) return -1;
    memcpy(img->code, blob + off, img->code_len);
    off += img->code_len;
    if (img->str_count > MAX_STRS) return -1;
    for (uint16_t i = 0; i < img->str_count; i++) {
        if (off + 2 > len) return -1;
        uint16_t n = rd_u16(blob + off); off += 2;
        if (off + n > len) return -1;
        img->strings[i] = (char *)malloc(n + 1);
        if (!img->strings[i]) return -1;
        memcpy(img->strings[i], blob + off, n);
        img->strings[i][n] = 0;
        off += n;
    }
    if (img->file_count > MAX_FILES) return -1;
    for (uint16_t i = 0; i < img->file_count; i++) {
        if (off >= len) return -1;
        uint8_t nl = blob[off++];
        if (off + nl + 2 > len || nl >= MAX_NAME) return -1;
        memcpy(img->files[i].name, blob + off, nl);
        img->files[i].name[nl] = 0;
        off += nl;
        uint16_t fl = rd_u16(blob + off); off += 2;
        if (off + fl > len || fl > sizeof(img->files[i].data)) return -1;
        memcpy(img->files[i].data, blob + off, fl);
        img->files[i].len = fl;
        off += fl;
    }
    return 0;
}

static StickFile *find_file(Image *img, const char *name) {
    for (uint16_t i = 0; i < img->file_count; i++)
        if (strcmp(img->files[i].name, name) == 0) return &img->files[i];
    return NULL;
}

static int ends_with_app(const char *name) {
    size_t n = strlen(name);
    return n >= 4 && strcmp(name + n - 4, ".app") == 0;
}

static int unpack_app(const uint8_t *blob, uint16_t len,
                      uint8_t *code, uint16_t *code_len,
                      char **strings, uint16_t *str_count) {
    if (len < 8 || blob[0] != 'A' || blob[1] != 'P' || blob[2] != 'P' || blob[3] != '1')
        return -1;
    uint16_t cl = rd_u16(blob + 4);
    uint16_t sc = rd_u16(blob + 6);
    size_t off = 8;
    if (off + cl > len || cl > MAX_CODE || sc > MAX_STRS) return -1;
    memcpy(code, blob + off, cl);
    off += cl;
    *code_len = cl;
    for (uint16_t i = 0; i < sc; i++) {
        if (off + 2 > len) return -1;
        uint16_t n = rd_u16(blob + off); off += 2;
        if (off + n > len) return -1;
        strings[i] = (char *)malloc(n + 1);
        if (!strings[i]) return -1;
        memcpy(strings[i], blob + off, n);
        strings[i][n] = 0;
        off += n;
    }
    *str_count = sc;
    return 0;
}

static void free_guest_strings(CPU *cpu) {
    if (!cpu->guest_owns_strings) return;
    for (uint16_t i = 0; i < cpu->str_count; i++) free(cpu->strings[i]);
    cpu->guest_owns_strings = 0;
}

static void leave_app(CPU *cpu);

static void enter_app(CPU *cpu, const char *name, const uint8_t *blob, uint16_t len) {
    if (cpu->fp >= MAX_FRAMES) { die_trap(cpu, "app nest"); return; }
    Frame *fr = &cpu->frames[cpu->fp++];
    memcpy(fr->code, cpu->code, cpu->code_len);
    fr->code_len = cpu->code_len;
    /* save string pointers (host strings stay owned by img) */
    for (uint16_t i = 0; i < cpu->str_count; i++) fr->strings[i] = cpu->strings[i];
    fr->str_count = cpu->str_count;
    fr->pc = cpu->pc;
    memcpy(fr->vars, cpu->vars, sizeof(cpu->vars));
    memcpy(fr->call, cpu->call, sizeof(cpu->call));
    fr->csp = cpu->csp;
    memcpy(fr->stack, cpu->stack, sizeof(cpu->stack));
    fr->sp = cpu->sp;
    fr->owns_strings = cpu->guest_owns_strings;

    uint8_t gcode[MAX_CODE];
    uint16_t gcl = 0;
    char *gstr[MAX_STRS];
    uint16_t gsc = 0;
    memset(gstr, 0, sizeof(gstr));
    if (unpack_app(blob, len, gcode, &gcl, gstr, &gsc) != 0) {
        cpu->fp--;
        uart_line("app bad format");
        return;
    }
    /* switch active */
    static uint8_t active_code[MAX_CODE];
    memcpy(active_code, gcode, gcl);
    cpu->code = active_code;
    cpu->code_len = gcl;
    /* stash guest string pointer array on heap via static slot — use malloc block */
    {
        char **hold = (char **)malloc(sizeof(char *) * MAX_STRS);
        if (!hold) { die_trap(cpu, "oom"); return; }
        for (uint16_t i = 0; i < gsc; i++) hold[i] = gstr[i];
        cpu->strings = hold;
        cpu->str_count = gsc;
        cpu->guest_owns_strings = 1;
    }
    cpu->pc = 0;
    memset(cpu->vars, 0, sizeof(cpu->vars));
    cpu->csp = 0;
    cpu->sp = 0;
    {
        char line[96];
        snprintf(line, sizeof(line), "--- app:%s ---", name);
        uart_line(line);
    }
}

static void drain_appq(CPU *cpu);

static void leave_app(CPU *cpu) {
    if (cpu->fp <= 0) return;
    free_guest_strings(cpu);
    if (cpu->guest_owns_strings == 0 && cpu->strings && cpu->strings != cpu->img.strings) {
        /* free the hold array */
        free(cpu->strings);
    }
    Frame *fr = &cpu->frames[--cpu->fp];
    /* restore host/kernel code into a static buffer if needed */
    static uint8_t host_code[MAX_CODE];
    if (cpu->fp == 0) {
        memcpy(host_code, cpu->img.code, cpu->img.code_len);
        cpu->code = host_code;
        cpu->code_len = cpu->img.code_len;
        cpu->strings = cpu->img.strings;
        cpu->str_count = cpu->img.str_count;
        cpu->guest_owns_strings = 0;
    } else {
        memcpy(host_code, fr->code, fr->code_len);
        cpu->code = host_code;
        cpu->code_len = fr->code_len;
        /* nested guest restore is rare; use saved pointers */
        cpu->strings = fr->strings;
        cpu->str_count = fr->str_count;
        cpu->guest_owns_strings = fr->owns_strings;
    }
    cpu->pc = fr->pc;
    memcpy(cpu->vars, fr->vars, sizeof(cpu->vars));
    memcpy(cpu->call, fr->call, sizeof(cpu->call));
    cpu->csp = fr->csp;
    memcpy(cpu->stack, fr->stack, sizeof(cpu->stack));
    cpu->sp = fr->sp;
    uart_line("--- app:done ---");
    drain_appq(cpu);
}

static void run_named_app(CPU *cpu, const char *name) {
    StickFile *f = find_file(&cpu->img, name);
    if (!f) {
        char line[96];
        snprintf(line, sizeof(line), "app missing: %s", name);
        uart_line(line);
        return;
    }
    enter_app(cpu, name, f->data, f->len);
}

static void drain_appq(CPU *cpu) {
    if (cpu->appq_n <= 0 || cpu->fp > 0) return;
    char name[MAX_NAME];
    strncpy(name, cpu->appq[0], MAX_NAME - 1);
    name[MAX_NAME - 1] = 0;
    memmove(cpu->appq[0], cpu->appq[1], (size_t)(cpu->appq_n - 1) * MAX_NAME);
    cpu->appq_n--;
    run_named_app(cpu, name);
}

static void run_all_apps(CPU *cpu) {
    if (cpu->appq_n > 0) return;
    for (uint16_t i = 0; i < cpu->img.file_count; i++) {
        if (ends_with_app(cpu->img.files[i].name) && cpu->appq_n < MAX_APPQ) {
            strncpy(cpu->appq[cpu->appq_n], cpu->img.files[i].name, MAX_NAME - 1);
            cpu->appq[cpu->appq_n][MAX_NAME - 1] = 0;
            cpu->appq_n++;
        }
    }
    /* sort names (simple bubble) for stable order */
    for (int a = 0; a < cpu->appq_n; a++)
        for (int b = a + 1; b < cpu->appq_n; b++)
            if (strcmp(cpu->appq[a], cpu->appq[b]) > 0) {
                char tmp[MAX_NAME];
                memcpy(tmp, cpu->appq[a], MAX_NAME);
                memcpy(cpu->appq[a], cpu->appq[b], MAX_NAME);
                memcpy(cpu->appq[b], tmp, MAX_NAME);
            }
    {
        char line[96];
        snprintf(line, sizeof(line), "runall: %d apps (adapt=%d)", cpu->appq_n, cpu->adapt_mode);
        uart_line(line);
    }
    if (cpu->appq_n == 0) uart_line("apps: (none)");
    else drain_appq(cpu);
}

static void boot_banner(CPU *cpu) {
    char line[128];
    snprintf(line, sizeof(line), "[%s] v%u  mem=%uKB",
             cpu->img.banner, cpu->img.version, cpu->img.mem_kb);
    uart_line(line);
    snprintf(line, sizeof(line), "stick: %u files  code=%uB",
             cpu->img.file_count, cpu->img.code_len);
    uart_line(line);
    uart_line("--- boot ---");
    uart_line("POWER: VBUS only — StickCPU autonomous");
}

static int step(CPU *cpu) {
    if (cpu->halted) return 0;
    if (cpu->pc >= cpu->code_len) {
        if (cpu->fp > 0) { leave_app(cpu); return 1; }
        snprintf(cpu->halt_reason, sizeof(cpu->halt_reason), "pc out of range");
        cpu->halted = 1;
        return 0;
    }
    uint8_t op = cpu->code[cpu->pc++];
    cpu->ticks++;

    switch (op) {
    case 0x00:
        if (cpu->fp > 0) { leave_app(cpu); return 1; }
        snprintf(cpu->halt_reason, sizeof(cpu->halt_reason), "halt");
        cpu->halted = 1;
        return 0;
    case 0x01: return 1;
    case 0x02: {
        int16_t v = rd_i16(cpu->code + cpu->pc); cpu->pc += 2;
        push(cpu, v); return !cpu->halted;
    }
    case 0x03: pop(cpu); return !cpu->halted;
    case 0x04:
        if (cpu->sp <= 0) { die_trap(cpu, "stack underflow"); return 0; }
        push(cpu, cpu->stack[cpu->sp - 1]); return !cpu->halted;
    case 0x05: {
        int32_t a = pop(cpu), b = pop(cpu);
        push(cpu, a); push(cpu, b); return !cpu->halted;
    }
    case 0x06: pop(cpu); return !cpu->halted;
    case 0x07: { int32_t b = pop(cpu), a = pop(cpu); push(cpu, a + b); return !cpu->halted; }
    case 0x08: { int32_t b = pop(cpu), a = pop(cpu); push(cpu, a - b); return !cpu->halted; }
    case 0x09: { int32_t b = pop(cpu), a = pop(cpu); push(cpu, a * b); return !cpu->halted; }
    case 0x0A: {
        int32_t b = pop(cpu), a = pop(cpu);
        if (!b) { die_trap(cpu, "divide by zero"); return 0; }
        push(cpu, a / b); return !cpu->halted;
    }
    case 0x0B: {
        int32_t b = pop(cpu), a = pop(cpu);
        if (!b) { die_trap(cpu, "mod by zero"); return 0; }
        push(cpu, a % b); return !cpu->halted;
    }
    case 0x0C: { int32_t b = pop(cpu), a = pop(cpu); push(cpu, a == b); return !cpu->halted; }
    case 0x0D: { int32_t b = pop(cpu), a = pop(cpu); push(cpu, a != b); return !cpu->halted; }
    case 0x0E: { int32_t b = pop(cpu), a = pop(cpu); push(cpu, a < b); return !cpu->halted; }
    case 0x0F: { int32_t b = pop(cpu), a = pop(cpu); push(cpu, a > b); return !cpu->halted; }
    case 0x10: { int32_t b = pop(cpu), a = pop(cpu); push(cpu, a <= b); return !cpu->halted; }
    case 0x11: { int32_t b = pop(cpu), a = pop(cpu); push(cpu, a >= b); return !cpu->halted; }
    case 0x12: push(cpu, pop(cpu) ? 0 : 1); return !cpu->halted;
    case 0x13: { int32_t b = pop(cpu), a = pop(cpu); push(cpu, (a && b) ? 1 : 0); return !cpu->halted; }
    case 0x14: { int32_t b = pop(cpu), a = pop(cpu); push(cpu, (a || b) ? 1 : 0); return !cpu->halted; }
    case 0x15: {
        uint8_t slot = cpu->code[cpu->pc++];
        cpu->vars[slot] = pop(cpu); return !cpu->halted;
    }
    case 0x16: {
        uint8_t slot = cpu->code[cpu->pc++];
        push(cpu, cpu->vars[slot]); return !cpu->halted;
    }
    case 0x17: {
        char buf[32];
        snprintf(buf, sizeof(buf), "%d", pop(cpu));
        uart_line(buf); return !cpu->halted;
    }
    case 0x18: {
        uint16_t idx = rd_u16(cpu->code + cpu->pc); cpu->pc += 2;
        if (idx >= cpu->str_count) { die_trap(cpu, "bad string"); return 0; }
        uart_line(cpu->strings[idx]); return !cpu->halted;
    }
    case 0x19: {
        int16_t rel = rd_i16(cpu->code + cpu->pc); cpu->pc += 2;
        cpu->pc = (uint16_t)(cpu->pc + rel); return 1;
    }
    case 0x1A: {
        int16_t rel = rd_i16(cpu->code + cpu->pc); cpu->pc += 2;
        if (pop(cpu) == 0) cpu->pc = (uint16_t)(cpu->pc + rel);
        return !cpu->halted;
    }
    case 0x1B: {
        int16_t rel = rd_i16(cpu->code + cpu->pc); cpu->pc += 2;
        if (pop(cpu) != 0) cpu->pc = (uint16_t)(cpu->pc + rel);
        return !cpu->halted;
    }
    case 0x1C: {
        uint16_t addr = rd_u16(cpu->code + cpu->pc); cpu->pc += 2;
        if (cpu->csp >= MAX_CALL) { die_trap(cpu, "call overflow"); return 0; }
        cpu->call[cpu->csp++] = cpu->pc;
        cpu->pc = addr; return 1;
    }
    case 0x1D:
        if (cpu->csp <= 0) {
            snprintf(cpu->halt_reason, sizeof(cpu->halt_reason), "return from empty call");
            cpu->halted = 1; return 0;
        }
        cpu->pc = cpu->call[--cpu->csp]; return 1;
    case 0x1E: {
        int32_t idx = pop(cpu);
        const char *name = (idx >= 0 && idx < cpu->str_count) ? cpu->strings[idx] : "";
        StickFile *f = find_file(&cpu->img, name);
        push(cpu, f ? f->len : 0); return !cpu->halted;
    }
    case 0x1F: {
        int32_t val = pop(cpu);
        int32_t idx = pop(cpu);
        const char *name = (idx >= 0 && idx < cpu->str_count) ? cpu->strings[idx] : "out";
        StickFile *f = find_file(&cpu->img, name);
        if (!f && cpu->img.file_count < MAX_FILES) {
            f = &cpu->img.files[cpu->img.file_count++];
            strncpy(f->name, name, MAX_NAME - 1);
        }
        if (f) {
            int n = snprintf((char *)f->data, sizeof(f->data), "%d", val);
            f->len = (uint16_t)((n > 0) ? n : 0);
        }
        push(cpu, 1); return !cpu->halted;
    }
    case 0x20: {
        char line[256];
        size_t pos = 0;
        pos += (size_t)snprintf(line + pos, sizeof(line) - pos, "files: ");
        if (cpu->img.file_count == 0)
            snprintf(line + pos, sizeof(line) - pos, "(empty)");
        else {
            for (uint16_t i = 0; i < cpu->img.file_count; i++) {
                if (i) pos += (size_t)snprintf(line + pos, sizeof(line) - pos, ", ");
                pos += (size_t)snprintf(line + pos, sizeof(line) - pos, "%s", cpu->img.files[i].name);
                if (pos >= sizeof(line) - 1) break;
            }
        }
        uart_line(line);
        push(cpu, cpu->img.file_count); return !cpu->halted;
    }
    case 0x21: {
        uint32_t used = cpu->img.code_len;
        for (uint16_t i = 0; i < cpu->img.file_count; i++) used += cpu->img.files[i].len;
        uint32_t mem = (uint32_t)cpu->img.mem_kb * 1024u;
        push(cpu, (int32_t)(mem > used ? mem - used : 0));
        return !cpu->halted;
    }
    case 0x22:
        push(cpu, (int32_t)cpu->ticks); return !cpu->halted;
    case 0x23: {
        char line[128];
        snprintf(line, sizeof(line),
                 "StickOS/%u SAY-native pendrive  image~%uKB arena",
                 cpu->img.version, cpu->img.mem_kb);
        uart_line(line); return 1;
    }
    case 0x24: {
        uint16_t idx = rd_u16(cpu->code + cpu->pc); cpu->pc += 2;
        if (idx >= cpu->str_count) { die_trap(cpu, "bad string"); return 0; }
        run_named_app(cpu, cpu->strings[idx]);
        return !cpu->halted;
    }
    case 0x25:
        run_all_apps(cpu);
        return !cpu->halted;
    case 0x26: {
        int32_t mode = pop(cpu);
        cpu->adapt_mode = (int)mode;
        const char *lab = mode == 0 ? "off" : mode == 1 ? "universal" : mode == 2 ? "chameleon" : "custom";
        char line[96];
        snprintf(line, sizeof(line), "adapt: mode=%d (%s)", cpu->adapt_mode, lab);
        uart_line(line);
        if (cpu->adapt_mode >= 2)
            uart_line("adapt: chameleon armed — will re-scan apps");
        return !cpu->halted;
    }
    default:
        die_trap(cpu, "illegal opcode");
        return 0;
    }
}

static int run_cpu(CPU *cpu) {
    boot_banner(cpu);
    while (!cpu->halted && cpu->ticks < 500000u) {
        if (!step(cpu)) break;
    }
    if (!cpu->halted) {
        snprintf(cpu->halt_reason, sizeof(cpu->halt_reason), "tick limit");
        cpu->halted = 1;
    }
    {
        char line[96];
        snprintf(line, sizeof(line), "--- halt: %s (%u ticks) ---",
                 cpu->halt_reason, cpu->ticks);
        uart_line(line);
    }
    return strcmp(cpu->halt_reason, "halt") == 0 ? 0 : 1;
}

int main(void) {
    CPU cpu;
    memset(&cpu, 0, sizeof(cpu));
    if (parse_image(&cpu.img, stick_rom, stick_rom_len) != 0) {
        uart_line("FIRMWARE: bad ROM image");
        return 2;
    }
    static uint8_t host_code[MAX_CODE];
    memcpy(host_code, cpu.img.code, cpu.img.code_len);
    cpu.code = host_code;
    cpu.code_len = cpu.img.code_len;
    cpu.strings = cpu.img.strings;
    cpu.str_count = cpu.img.str_count;
    cpu.pc = cpu.img.entry;
    int rc = run_cpu(&cpu);
    for (uint16_t i = 0; i < cpu.img.str_count; i++) free(cpu.img.strings[i]);
    return rc;
}
