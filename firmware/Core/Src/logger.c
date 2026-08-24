#include "logger.h"
#include "fatfs.h"
#include <string.h>

FATFS fs;
FIL fil;

void Logger_Init(void) {
    // Mount the SD Card
    if (f_mount(&fs, "", 1) == FR_OK) {
        // Create or clear the log file on boot
        if (f_open(&fil, "log.csv", FA_CREATE_ALWAYS | FA_WRITE) == FR_OK) {
            const char* header = "Time,AccX,AccY,AccZ,MagX,MagY,MagZ,Press,Lat,Lon\n";
            UINT bw;
            f_write(&fil, header, strlen(header), &bw);
            f_close(&fil);
        }
    }
}

void Logger_LogData(const char* data) {
    UINT bw;
    // Open in append mode
    if (f_open(&fil, "log.csv", FA_OPEN_APPEND | FA_WRITE) == FR_OK) {
        f_write(&fil, data, strlen(data), &bw);
        f_close(&fil);
    }
}
