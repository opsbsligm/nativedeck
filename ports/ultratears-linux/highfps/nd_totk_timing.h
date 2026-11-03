#pragma once
#include "cpu.h"
#include <string.h>
float nd_totk_step(float hz);
static inline float nd_totk_reg(Cpu *c, unsigned reg) {
    float f; memcpy(&f, &c->v[reg], sizeof f); return f;
}
void f_8002a0e40(Cpu *c);
