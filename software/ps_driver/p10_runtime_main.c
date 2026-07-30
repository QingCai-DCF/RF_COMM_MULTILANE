/* Role-bound P10 entry point.  The build copies the reviewed P9 runtime
 * implementation as p9_runtime_main.inc so P9 and P10 share one DMA/cache/
 * mailbox implementation while P10 compiles the independent endpoint path. */
#include "p10_runtime_role.h"
#include "p9_runtime_main.inc"
