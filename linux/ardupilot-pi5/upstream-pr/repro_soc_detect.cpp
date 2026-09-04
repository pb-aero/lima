// Standalone reproduction of UtilRPI::_get_board_type_using_peripheral_base()
// from libraries/AP_HAL_Linux/Util_RPI.cpp, master ff37fde.
// Only the directory-scan fallback is reproduced; N is the strncmp length under test.
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <dirent.h>

static uint32_t detect(int N)
{
    FILE *fp; uint32_t base = 0; unsigned char buf[32];
    fp = fopen("/proc/device-tree/soc/ranges", "rb");
    if (!fp) {
        const char *base_path = "/proc/device-tree";
        DIR *dir = opendir(base_path);
        if (!dir) { printf("    device-tree directory not found\n"); return 0; }
        struct dirent *entry; char ranges_path[256] {};
        while ((entry = readdir(dir)) != nullptr) {
            if (strncmp(entry->d_name, "soc", N) == 0) {
                snprintf(ranges_path, sizeof(ranges_path), "%s/%s/ranges", base_path, entry->d_name);
                break;
            }
        }
        closedir(dir);
        if (ranges_path[0] == 0) { printf("    \"ranges\" file not found\n"); return 0; }
        printf("    matched node -> %s\n", ranges_path);
        fp = fopen(ranges_path, "rb");
    }
    if (fp) {
        const uint16_t len = fread(buf, 1, sizeof(buf), fp);
        if (len >= 8) {
            base = buf[4]<<24 | buf[5]<<16 | buf[6]<<8 | buf[7];
            if (!base) base = buf[8]<<24 | buf[9]<<16 | buf[10]<<8 | buf[11];
            if (!base && (len>15)) base = buf[12]<<24 | buf[13]<<16 | buf[14]<<8 | buf[15];
        }
        fclose(fp);
    }
    return base;
}

static void report(int N)
{
    printf("strncmp(d_name, \"soc\", %d):\n", N);
    uint32_t base = detect(N);
    printf("    base = 0x%x -> ", base);
    switch (base) {
        case 0x0:        printf("UNKNOWN_BOARD  (\"Cannot detect board-type\")\n"); break;
        case 0x10:       printf("RPI_5\n"); break;
        case 0x20000000: printf("RPI_ZERO_1\n"); break;
        case 0x3f000000: printf("RPI_2_3_ZERO2\n"); break;
        case 0xfe000000: printf("RPI_4\n"); break;
        default:         printf("unmapped\n"); break;
    }
}

int main() {
    printf("kernel node names present:\n");
    printf("uname/model checked separately.\n\n");
    report(4);   // upstream as written -- exact match for "soc"
    printf("\n");
    report(3);   // proposed fix -- prefix match
    return 0;
}
