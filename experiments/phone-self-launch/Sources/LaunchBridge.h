#include <stdint.h>
#include <stddef.h>
int32_t ipu_self_launch_start(const uint8_t *, size_t, const uint8_t *, size_t);
int32_t ipu_self_launch_pair_start(const uint8_t *, size_t);
int32_t ipu_self_launch_submit_pin(const uint8_t *, size_t);
size_t ipu_self_launch_take_record(uint8_t *, size_t);
void ipu_self_launch_stop(void);
size_t ipu_self_launch_status(uint8_t *, size_t);
