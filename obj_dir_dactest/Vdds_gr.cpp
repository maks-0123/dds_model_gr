// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Vdds_gr__pch.h"

//============================================================
// Constructors

Vdds_gr::Vdds_gr(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Vdds_gr__Syms(contextp(), _vcname__, this)}
    , m_evalLoop{*this, /*convergeLimit:*/ 10000}
    , clock{vlSymsp->TOP.clock}
    , reset{vlSymsp->TOP.reset}
    , io_in{vlSymsp->TOP.io_in}
    , io_out{vlSymsp->TOP.io_out}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
}

Vdds_gr::Vdds_gr(const char* _vcname__)
    : Vdds_gr(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Vdds_gr::~Vdds_gr() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Vdds_gr___024root___eval_debug_assertions(Vdds_gr___024root* vlSelf);
#endif  // VL_DEBUG
VL_ATTR_COLD void Vdds_gr___024root___eval_static(Vdds_gr___024root* vlSelf);
VL_ATTR_COLD void Vdds_gr___024root___eval_initial(Vdds_gr___024root* vlSelf);
VL_ATTR_COLD bool Vdds_gr___024root___eval_stl(Vdds_gr___024root* vlSelf, CData/*0:0*/ firstIteration);
void Vdds_gr___024root___eval_sample(Vdds_gr___024root* vlSelf);
bool Vdds_gr___024root___eval_ico(Vdds_gr___024root* vlSelf, CData/*0:0*/ firstIteration);
bool Vdds_gr___024root___eval_act(Vdds_gr___024root* vlSelf);
bool Vdds_gr___024root___eval_inact(Vdds_gr___024root* vlSelf);
bool Vdds_gr___024root___eval_nba(Vdds_gr___024root* vlSelf);
bool Vdds_gr___024root___eval_obs(Vdds_gr___024root* vlSelf);
bool Vdds_gr___024root___eval_react(Vdds_gr___024root* vlSelf);
void Vdds_gr___024root___eval_postponed(Vdds_gr___024root* vlSelf);
VL_ATTR_COLD void Vdds_gr___024root___eval_final(Vdds_gr___024root* vlSelf);
VL_ATTR_COLD void Vdds_gr___024root___eval_dump_triggers__stl(Vdds_gr___024root* vlSelf);
VL_ATTR_COLD void Vdds_gr___024root___eval_dump_triggers__ico(Vdds_gr___024root* vlSelf);
VL_ATTR_COLD void Vdds_gr___024root___eval_dump_triggers__act(Vdds_gr___024root* vlSelf);
VL_ATTR_COLD void Vdds_gr___024root___eval_dump_triggers__nba(Vdds_gr___024root* vlSelf);
VL_ATTR_COLD void Vdds_gr___024root___eval_dump_triggers__obs(Vdds_gr___024root* vlSelf);
VL_ATTR_COLD void Vdds_gr___024root___eval_dump_triggers__react(Vdds_gr___024root* vlSelf);

void Vdds_gr::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Vdds_gr::eval_step\n"); );
    m_evalLoop.eval();
}

void Vdds_gr::evalBegin() {
#ifdef VL_DEBUG
    // Debug assertions
    Vdds_gr___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_deleter.deleteAll();
}

void Vdds_gr::evalEnd() {
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
}

void Vdds_gr::evalStatic() {
    Vdds_gr___024root___eval_static(&(vlSymsp->TOP));
}

void Vdds_gr::evalInitial() {
    Vdds_gr___024root___eval_initial(&(vlSymsp->TOP));
}

bool Vdds_gr::evalStl(bool firstIteration) {
    return Vdds_gr___024root___eval_stl(&(vlSymsp->TOP), firstIteration);
}

void Vdds_gr::evalSample() {
    Vdds_gr___024root___eval_sample(&(vlSymsp->TOP));
}

bool Vdds_gr::evalIco(bool firstIteration) {
    return Vdds_gr___024root___eval_ico(&(vlSymsp->TOP), firstIteration);
}

bool Vdds_gr::evalAct() {
    return Vdds_gr___024root___eval_act(&(vlSymsp->TOP));
}

bool Vdds_gr::evalInact() {
    return Vdds_gr___024root___eval_inact(&(vlSymsp->TOP));
}

bool Vdds_gr::evalNba() {
    return Vdds_gr___024root___eval_nba(&(vlSymsp->TOP));
}

bool Vdds_gr::evalObs() {
    return Vdds_gr___024root___eval_obs(&(vlSymsp->TOP));
}

bool Vdds_gr::evalReact() {
    return Vdds_gr___024root___eval_react(&(vlSymsp->TOP));
}

void Vdds_gr::evalPostponed() {
    Vdds_gr___024root___eval_postponed(&(vlSymsp->TOP));
}

void Vdds_gr::evalFinal() {
    Vdds_gr___024root___eval_final(&(vlSymsp->TOP));
}

VL_ATTR_COLD void Vdds_gr::dumpTriggersStl() {
    Vdds_gr___024root___eval_dump_triggers__stl(&(vlSymsp->TOP));
}

VL_ATTR_COLD void Vdds_gr::dumpTriggersIco() {
    Vdds_gr___024root___eval_dump_triggers__ico(&(vlSymsp->TOP));
}

VL_ATTR_COLD void Vdds_gr::dumpTriggersAct() {
    Vdds_gr___024root___eval_dump_triggers__act(&(vlSymsp->TOP));
}

VL_ATTR_COLD void Vdds_gr::dumpTriggersNba() {
    Vdds_gr___024root___eval_dump_triggers__nba(&(vlSymsp->TOP));
}

VL_ATTR_COLD void Vdds_gr::dumpTriggersObs() {
    Vdds_gr___024root___eval_dump_triggers__obs(&(vlSymsp->TOP));
}

VL_ATTR_COLD void Vdds_gr::dumpTriggersReact() {
    Vdds_gr___024root___eval_dump_triggers__react(&(vlSymsp->TOP));
}

//============================================================
// Events and timing
bool Vdds_gr::eventsPending() { return false; }

uint64_t Vdds_gr::nextTimeSlot() {
    VL_FATAL_MT(__FILE__, __LINE__, "", "No delays in the design");
    return 0;
}

//============================================================
// Utilities

const char* Vdds_gr::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

VL_ATTR_COLD void Vdds_gr::final() {
    contextp()->executingFinal(true);
    evalFinal();
    contextp()->executingFinal(false);
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Vdds_gr::hierName() const { return vlSymsp->name(); }
const char* Vdds_gr::modelName() const { return "Vdds_gr"; }
unsigned Vdds_gr::threads() const { return 1; }
void Vdds_gr::prepareClone() const { contextp()->prepareClone(); }
void Vdds_gr::atClone() const {
    contextp()->threadPoolpOnClone();
}
