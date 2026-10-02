// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table internal header
//
// Internal details; most calling programs do not need this header,
// unless using verilator public meta comments.

#ifndef VERILATED_VDDS_GR__SYMS_H_
#define VERILATED_VDDS_GR__SYMS_H_  // guard

#include "verilated.h"

// INCLUDE MODEL CLASS

#include "Vdds_gr.h"

// INCLUDE MODULE CLASSES
#include "Vdds_gr___024root.h"

// SYMS CLASS (contains all model state)
class alignas(VL_CACHE_LINE_BYTES) Vdds_gr__Syms final : public VerilatedSyms {
  public:
    // INTERNAL STATE
    Vdds_gr* const __Vm_modelp;
    VlDeleter __Vm_deleter;
    bool& __Vm_didInit;

    // MODULE INSTANCE STATE
    Vdds_gr___024root              TOP;

    // CONSTRUCTORS
    Vdds_gr__Syms(VerilatedContext* contextp, const char* namep, Vdds_gr* modelp);
    ~Vdds_gr__Syms();

    // METHODS
    const char* name() const { return TOP.vlNamep; }
};

#endif  // guard
