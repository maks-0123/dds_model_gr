#include <cstdint>
#include "Vdds_gr.h"
#include "verilated.h"

static Vdds_gr* top = nullptr;

static void tick() {
    top->clock = 1; top->eval();
    top->clock = 0; top->eval();
}

extern "C" {
void dds_init() {
    top = new Vdds_gr;
    top->clock = 0;
    top->reset = 1;
    top->io_in = 0;
    top->eval();
    for (int i = 0; i < 4; i++) tick();
    top->reset = 0;
}

void dds_run(const int32_t* in, int32_t* out, int n) {
    
    for (int i = 0; i < n; i++) {
        top->io_in = (uint32_t)in[i];
        tick();
        out[i] = (int32_t)top->io_out;
    }
}
}