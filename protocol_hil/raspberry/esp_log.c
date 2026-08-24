#define _POSIX_C_SOURCE 200809L

#include <arpa/inet.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

#define DEFAULT_DEBUG_PORT 4211
#define MAX_EVENT_BYTES 512

int main(int argc, char **argv)
{
    const int port = argc > 1 ? atoi(argv[1]) : DEFAULT_DEBUG_PORT;
    if (port < 1024 || port > UINT16_MAX) {
        fputs("invalid diagnostic UDP port\n", stderr);
        return EXIT_FAILURE;
    }

    const int socket_fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (socket_fd < 0) {
        perror("socket");
        return EXIT_FAILURE;
    }
    const int reuse = 1;
    (void)setsockopt(socket_fd, SOL_SOCKET, SO_REUSEADDR,
                     &reuse, sizeof(reuse));
    const struct sockaddr_in local = {
        .sin_family = AF_INET,
        .sin_port = htons((uint16_t)port),
        .sin_addr.s_addr = htonl(INADDR_ANY),
    };
    if (bind(socket_fd, (const struct sockaddr *)&local, sizeof(local)) != 0) {
        perror("bind");
        close(socket_fd);
        return EXIT_FAILURE;
    }

    setvbuf(stdout, NULL, _IOLBF, 0);
    printf("ESP32 HIL diagnostic events on UDP %d\n", port);
    for (;;) {
        char event[MAX_EVENT_BYTES];
        const ssize_t length = recvfrom(
            socket_fd, event, sizeof(event) - 1U, 0, NULL, NULL
        );
        if (length < 0) {
            if (errno == EINTR) {
                continue;
            }
            perror("recvfrom");
            close(socket_fd);
            return EXIT_FAILURE;
        }
        event[length] = '\0';
        puts(event);
    }
}
