// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vdds_gr.h for the primary calling header

#ifndef VERILATED_VDDS_GR___024ROOT_H_
#define VERILATED_VDDS_GR___024ROOT_H_  // guard

#include "verilated.h"


class Vdds_gr__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vdds_gr___024root final {
  public:

    // DESIGN SPECIFIC STATE
    VL_IN8(clock,0,0);
    VL_IN8(reset,0,0);
    CData/*0:0*/ __Vtrigprevexpr___TOP__clock__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__reset__0;
    CData/*0:0*/ __VicoDidInit;
    CData/*0:0*/ __Vtrigprevexpr___TOP__clock__1;
    SData/*15:0*/ dds_gr__DOT__held;
    VL_IN(io_in,31,0);
    VL_OUT(io_out,31,0);
    IData/*16:0*/ dds_gr__DOT__u2__DOT__acc;
    IData/*31:0*/ __Vtrigprevexpr___TOP__io_in__0;
    VlUnpacked<QData/*63:0*/, 1> __VstlTriggered;
    VlUnpacked<QData/*63:0*/, 2> __VicoTriggered;
    VlUnpacked<QData/*63:0*/, 1> __VactTriggered;
    VlUnpacked<QData/*63:0*/, 1> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vdds_gr__Syms* vlSymsp;
    const char* vlNamep;

    // CONSTRUCTORS
    Vdds_gr___024root(Vdds_gr__Syms* symsp, const char* namep);
    ~Vdds_gr___024root();
    VL_UNCOPYABLE(Vdds_gr___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
