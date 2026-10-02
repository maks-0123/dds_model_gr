// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vdds_gr.h for the primary calling header

#include "Vdds_gr__pch.h"

VL_ATTR_COLD void Vdds_gr___024root___eval_static(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_static\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__Vtrigprevexpr___TOP__clock__0 = vlSelfRef.clock;
    vlSelfRef.__Vtrigprevexpr___TOP__reset__0 = vlSelfRef.reset;
    vlSelfRef.__Vtrigprevexpr___TOP__io_in__0 = vlSelfRef.io_in;
    vlSelfRef.__Vtrigprevexpr___TOP__clock__1 = vlSelfRef.clock;
}

VL_ATTR_COLD void Vdds_gr___024root___eval_initial(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_initial\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vdds_gr___024root___dump_triggers__stl(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG
VL_ATTR_COLD bool Vdds_gr___024root___trigger_anySet__stl(const VlUnpacked<QData/*63:0*/, 1> &in);

VL_ATTR_COLD bool Vdds_gr___024root___eval_stl(Vdds_gr___024root* vlSelf, CData/*0:0*/ firstIteration) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_stl\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VstlExecute;
    // Body
    vlSelfRef.__VstlTriggered[0U] = ((0xfffffffffffffffeULL 
                                      & vlSelfRef.__VstlTriggered[0U]) 
                                     | (IData)((IData)(firstIteration)));
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vdds_gr___024root___dump_triggers__stl(vlSelfRef.__VstlTriggered, "stl"s);
    }
#endif
    __VstlExecute = Vdds_gr___024root___trigger_anySet__stl(vlSelfRef.__VstlTriggered);
    if (__VstlExecute) {
        {
            // Inlined CFunc: _eval_body__stl
            if ((1ULL & vlSelfRef.__VstlTriggered[0U])) {
                {
                    // Inlined CFunc: _stl_sequent__TOP__0
                    vlSelfRef.io_out = (((- (IData)(
                                                    (1U 
                                                     & (vlSelfRef.dds_gr__DOT__u2__DOT__acc 
                                                        >> 0x00000010U)))) 
                                         << 0x00000010U) 
                                        | (0x0000ffffU 
                                           & (vlSelfRef.dds_gr__DOT__u2__DOT__acc 
                                              >> 1U)));
                }
            }
        }
    }
    return (__VstlExecute);
}

VL_ATTR_COLD void Vdds_gr___024root___eval_dump_triggers__stl(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_dump_triggers__stl\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
#ifdef VL_DEBUG
    Vdds_gr___024root___dump_triggers__stl(vlSelfRef.__VstlTriggered, "stl"s);
#endif
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vdds_gr___024root___dump_triggers__ico(const VlUnpacked<QData/*63:0*/, 2> &triggers, const std::string &tag);
#endif  // VL_DEBUG

VL_ATTR_COLD void Vdds_gr___024root___eval_dump_triggers__ico(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_dump_triggers__ico\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
#ifdef VL_DEBUG
    Vdds_gr___024root___dump_triggers__ico(vlSelfRef.__VicoTriggered, "ico"s);
#endif
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vdds_gr___024root___dump_triggers__act(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG

VL_ATTR_COLD void Vdds_gr___024root___eval_dump_triggers__act(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_dump_triggers__act\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
#ifdef VL_DEBUG
    Vdds_gr___024root___dump_triggers__act(vlSelfRef.__VactTriggered, "act"s);
#endif
}

VL_ATTR_COLD void Vdds_gr___024root___eval_dump_triggers__nba(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_dump_triggers__nba\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
#ifdef VL_DEBUG
    Vdds_gr___024root___dump_triggers__act(vlSelfRef.__VnbaTriggered, "nba"s);
#endif
}

VL_ATTR_COLD void Vdds_gr___024root___eval_dump_triggers__obs(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_dump_triggers__obs\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

VL_ATTR_COLD void Vdds_gr___024root___eval_dump_triggers__react(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_dump_triggers__react\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

VL_ATTR_COLD void Vdds_gr___024root___eval_final(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_final\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vdds_gr___024root___dump_triggers__stl(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___dump_triggers__stl\n"); );
    // Body
    if ((1U & (~ (IData)(Vdds_gr___024root___trigger_anySet__stl(triggers))))) {
        VL_DBG_MSGS("         No '" + tag + "' region triggers active\n");
    }
    if ((1U & (IData)(triggers[0U]))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 0 is active: Internal 'stl' trigger - first iteration\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD bool Vdds_gr___024root___trigger_anySet__stl(const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___trigger_anySet__stl\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        if (in[n]) {
            return (1U);
        }
        n = ((IData)(1U) + n);
    } while ((1U > n));
    return (0U);
}

bool Vdds_gr___024root___trigger_anySet__ico(const VlUnpacked<QData/*63:0*/, 2> &in);

#ifdef VL_DEBUG
VL_ATTR_COLD void Vdds_gr___024root___dump_triggers__ico(const VlUnpacked<QData/*63:0*/, 2> &triggers, const std::string &tag) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___dump_triggers__ico\n"); );
    // Body
    if ((1U & (~ (IData)(Vdds_gr___024root___trigger_anySet__ico(triggers))))) {
        VL_DBG_MSGS("         No '" + tag + "' region triggers active\n");
    }
    if ((1U & (IData)(triggers[0U]))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 0 is active: @( clock)\n");
    }
    if ((1U & (IData)((triggers[0U] >> 1U)))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 1 is active: @( reset)\n");
    }
    if ((1U & (IData)((triggers[0U] >> 2U)))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 2 is active: @( io_in)\n");
    }
    if ((1U & (IData)(triggers[1U]))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 64 is active: Internal 'ico' trigger - first iteration\n");
    }
}
#endif  // VL_DEBUG

bool Vdds_gr___024root___trigger_anySet__act(const VlUnpacked<QData/*63:0*/, 1> &in);

#ifdef VL_DEBUG
VL_ATTR_COLD void Vdds_gr___024root___dump_triggers__act(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___dump_triggers__act\n"); );
    // Body
    if ((1U & (~ (IData)(Vdds_gr___024root___trigger_anySet__act(triggers))))) {
        VL_DBG_MSGS("         No '" + tag + "' region triggers active\n");
    }
    if ((1U & (IData)(triggers[0U]))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 0 is active: @(posedge clock)\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Vdds_gr___024root___ctor_var_reset(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___ctor_var_reset\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    const uint64_t __VscopeHash = VL_MURMUR64_HASH(vlSelf->vlNamep);
    vlSelf->clock = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 5452235342940299466ull);
    vlSelf->reset = VL_SCOPED_RAND_RESET_I(1, __VscopeHash, 9928399931838511862ull);
    vlSelf->io_in = VL_SCOPED_RAND_RESET_I(32, __VscopeHash, 13661171322661826680ull);
    vlSelf->io_out = VL_SCOPED_RAND_RESET_I(32, __VscopeHash, 2660750564050360070ull);
    vlSelf->dds_gr__DOT__held = VL_SCOPED_RAND_RESET_I(16, __VscopeHash, 13113629741124689966ull);
    vlSelf->dds_gr__DOT__u2__DOT__acc = VL_SCOPED_RAND_RESET_I(17, __VscopeHash, 16775178943530284201ull);
    for (int __Vi0 = 0; __Vi0 < 1; ++__Vi0) {
        vlSelf->__VstlTriggered[__Vi0] = 0;
    }
    for (int __Vi0 = 0; __Vi0 < 2; ++__Vi0) {
        vlSelf->__VicoTriggered[__Vi0] = 0;
    }
    vlSelf->__Vtrigprevexpr___TOP__clock__0 = 0;
    vlSelf->__Vtrigprevexpr___TOP__reset__0 = 0;
    vlSelf->__Vtrigprevexpr___TOP__io_in__0 = 0;
    vlSelf->__VicoDidInit = 0;
    for (int __Vi0 = 0; __Vi0 < 1; ++__Vi0) {
        vlSelf->__VactTriggered[__Vi0] = 0;
    }
    vlSelf->__Vtrigprevexpr___TOP__clock__1 = 0;
    for (int __Vi0 = 0; __Vi0 < 1; ++__Vi0) {
        vlSelf->__VnbaTriggered[__Vi0] = 0;
    }
}
