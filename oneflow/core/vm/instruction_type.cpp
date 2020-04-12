#include "oneflow/core/vm/instr_type_id.h"
#include "oneflow/core/vm/instruction_type.h"
#include "oneflow/core/vm/instruction.msg.h"
#include "oneflow/core/common/util.h"

namespace oneflow {
namespace vm {

namespace {

HashMap<std::string, InstrTypeId>* InstrTypeId4InstructionName() {
  static HashMap<std::string, InstrTypeId> map;
  return &map;
}

}  // namespace

void InstructionType::Compute(Scheduler* scheduler, InstrCtx* instr_ctx) const {
  Compute(scheduler, instr_ctx->mut_instr_msg());
}

void InstructionType::Infer(Scheduler* scheduler, InstrCtx* instr_ctx) const {
  Infer(scheduler, instr_ctx->mut_instr_msg());
}

const InstrTypeId& LookupInstrTypeId(const std::string& name) {
  const auto& map = *InstrTypeId4InstructionName();
  const auto& iter = map.find(name);
  CHECK(iter != map.end());
  return iter->second;
}

void ForEachInstrTypeId(std::function<void(const InstrTypeId&)> DoEach) {
  for (const auto& pair : *InstrTypeId4InstructionName()) { DoEach(pair.second); }
}

HashMap<std::type_index, const InstructionType*>* InstructionType4TypeIndex() {
  static HashMap<std::type_index, const InstructionType*> map;
  return &map;
}

void RegisterInstrTypeId(const std::string& instruction_name, const StreamType* stream_type,
                         const InstructionType* instruction_type, InterpretType interpret_type,
                         VmType vm_type) {
  InstrTypeId instr_type_id;
  instr_type_id.__Init__(stream_type, instruction_type, interpret_type, vm_type);
  CHECK(InstrTypeId4InstructionName()->emplace(instruction_name, instr_type_id).second);
}

}  // namespace vm
}  // namespace oneflow