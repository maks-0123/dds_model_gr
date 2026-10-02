// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vdds_gr.h for the primary calling header

#include "Vdds_gr__pch.h"

void Vdds_gr___024root___eval_sample(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_sample\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vdds_gr___024root___dump_triggers__ico(const VlUnpacked<QData/*63:0*/, 2> &triggers, const std::string &tag);
#endif  // VL_DEBUG

bool Vdds_gr___024root___eval_ico(Vdds_gr___024root* vlSelf, CData/*0:0*/ firstIteration) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_ico\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VicoTriggered[1U] = ((0xfffffffffffffffeULL 
                                      & vlSelfRef.__VicoTriggered[1U]) 
                                     | (IData)((IData)(firstIteration)));
    {
        // Inlined CFunc: _eval_triggers_vec__ico
        vlSelfRef.__VicoTriggered[0U] = (QData)((IData)(
                                                        (((vlSelfRef.io_in 
                                                           != vlSelfRef.__Vtrigprevexpr___TOP__io_in__0) 
                                                          << 2U) 
                                                         | ((((IData)(vlSelfRef.reset) 
                                                              != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__reset__0)) 
                                                             << 1U) 
                                                            | ((IData)(vlSelfRef.clock) 
                                                               != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__clock__0))))));
        vlSelfRef.__Vtrigprevexpr___TOP__clock__0 = vlSelfRef.clock;
        vlSelfRef.__Vtrigprevexpr___TOP__reset__0 = vlSelfRef.reset;
        vlSelfRef.__Vtrigprevexpr___TOP__io_in__0 = vlSelfRef.io_in;
        if (VL_UNLIKELY(((1U & (~ (IData)(vlSelfRef.__VicoDidInit)))))) {
            vlSelfRef.__VicoDidInit = 1U;
            vlSelfRef.__VicoTriggered[0U] = (1ULL | vlSelfRef.__VicoTriggered[0U]);
            vlSelfRef.__VicoTriggered[0U] = (2ULL | vlSelfRef.__VicoTriggered[0U]);
            vlSelfRef.__VicoTriggered[0U] = (4ULL | vlSelfRef.__VicoTriggered[0U]);
        }
    }
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vdds_gr___024root___dump_triggers__ico(vlSelfRef.__VicoTriggered, "ico"s);
    }
#endif
    return (0U);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vdds_gr___024root___dump_triggers__act(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG
void Vdds_gr___024root___trigger_orInto__act_vec_vec(VlUnpacked<QData/*63:0*/, 1> &out, const VlUnpacked<QData/*63:0*/, 1> &in);

bool Vdds_gr___024root___eval_act(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_act\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    {
        // Inlined CFunc: _eval_triggers_vec__act
        vlSelfRef.__VactTriggered[0U] = (QData)((IData)(
                                                        ((IData)(vlSelfRef.clock) 
                                                         & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__clock__1)))));
        vlSelfRef.__Vtrigprevexpr___TOP__clock__1 = vlSelfRef.clock;
    }
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vdds_gr___024root___dump_triggers__act(vlSelfRef.__VactTriggered, "act"s);
    }
#endif
    Vdds_gr___024root___trigger_orInto__act_vec_vec(vlSelfRef.__VnbaTriggered, vlSelfRef.__VactTriggered);
    return (0U);
}

bool Vdds_gr___024root___eval_inact(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_inact\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    return (0U);
}

bool Vdds_gr___024root___trigger_anySet__act(const VlUnpacked<QData/*63:0*/, 1> &in);
void Vdds_gr___024root___trigger_clear__act(VlUnpacked<QData/*63:0*/, 1> &out);

bool Vdds_gr___024root___eval_nba(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_nba\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = Vdds_gr___024root___trigger_anySet__act(vlSelfRef.__VnbaTriggered);
    if (__VnbaExecute) {
        {
            // Inlined CFunc: _eval_body__nba
            if ((1ULL & vlSelfRef.__VnbaTriggered[0U])) {
                {
                    // Inlined CFunc: _nba_sequent__TOP__0
                    vlSelfRef.dds_gr__DOT__u2__DOT__acc 
                        = ((IData)(vlSelfRef.reset)
                            ? 0U : (0x0001ffffU & (vlSelfRef.dds_gr__DOT__u2__DOT__acc 
                                                   + 
                                                   (((0x00010000U 
                                                      & ((IData)(vlSelfRef.dds_gr__DOT__held) 
                                                         << 1U)) 
                                                     | (IData)(vlSelfRef.dds_gr__DOT__held)) 
                                                    - 
                                                    ((0x00010000U 
                                                      & vlSelfRef.dds_gr__DOT__u2__DOT__acc) 
                                                     | (0x0000ffffU 
                                                        & (vlSelfRef.dds_gr__DOT__u2__DOT__acc 
                                                           >> 1U)))))));
                    vlSelfRef.io_out = (((- (IData)(
                                                    (1U 
                                                     & (vlSelfRef.dds_gr__DOT__u2__DOT__acc 
                                                        >> 0x00000010U)))) 
                                         << 0x00000010U) 
                                        | (0x0000ffffU 
                                           & (vlSelfRef.dds_gr__DOT__u2__DOT__acc 
                                              >> 1U)));
                    vlSelfRef.dds_gr__DOT__held = (0x0000ffffU 
                                                   & vlSelfRef.io_in);
                }
            }
        }
        Vdds_gr___024root___trigger_clear__act(vlSelfRef.__VnbaTriggered);
    }
    return (__VnbaExecute);
}

bool Vdds_gr___024root___eval_obs(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_obs\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    return (0U);
}

bool Vdds_gr___024root___eval_react(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_react\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    return (0U);
}

void Vdds_gr___024root___eval_postponed(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_postponed\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

bool Vdds_gr___024root___trigger_anySet__ico(const VlUnpacked<QData/*63:0*/, 2> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___trigger_anySet__ico\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        if (in[n]) {
            return (1U);
        }
        n = ((IData)(1U) + n);
    } while ((2U > n));
    return (0U);
}

bool Vdds_gr___024root___trigger_anySet__act(const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___trigger_anySet__act\n"); );
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

void Vdds_gr___024root___trigger_orInto__act_vec_vec(VlUnpacked<QData/*63:0*/, 1> &out, const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___trigger_orInto__act_vec_vec\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        out[n] = (out[n] | in[n]);
        n = ((IData)(1U) + n);
    } while ((0U >= n));
}

void Vdds_gr___024root___trigger_clear__act(VlUnpacked<QData/*63:0*/, 1> &out) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___trigger_clear__act\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        out[n] = 0ULL;
        n = ((IData)(1U) + n);
    } while ((1U > n));
}

#ifdef VL_DEBUG
void Vdds_gr___024root___eval_debug_assertions(Vdds_gr___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vdds_gr___024root___eval_debug_assertions\n"); );
    Vdds_gr__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if (VL_UNLIKELY(((vlSelfRef.clock & 0xfeU)))) {
        Verilated::overWidthError("clock");
    }
    if (VL_UNLIKELY(((vlSelfRef.reset & 0xfeU)))) {
        Verilated::overWidthError("reset");
    }
}
#endif  // VL_DEBUG
