// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vdds_gr.h for the primary calling header

#include "Vdds_gr__pch.h"

void Vdds_gr___024root___ctor_var_reset(Vdds_gr___024root* vlSelf);

Vdds_gr___024root::Vdds_gr___024root(Vdds_gr__Syms* symsp, const char* namep)
 {
    vlSymsp = symsp;
    vlNamep = strdup(namep);
    // Reset structure values
    Vdds_gr___024root___ctor_var_reset(this);
}

void Vdds_gr___024root::__Vconfigure(bool first) {
    (void)first;  // Prevent unused variable warning
}

Vdds_gr___024root::~Vdds_gr___024root() {
    VL_DO_DANGLING(std::free(const_cast<char*>(vlNamep)), vlNamep);
}
