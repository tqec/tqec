OPENQASM 2.0;
include "qelib1.inc";

// 8 qubit register (7 data qubits + 1 ancilla)
qreg q[8];
creg c[3];  // Classical register for 3 measurement outcomes

// Reset all qubits to |0⟩
reset q[0];
reset q[1];
reset q[2];
reset q[3];
reset q[4];
reset q[5];
reset q[6];
reset q[7];

// First stabilizer measurement (X₁X₂X₃X₄)
// Prepare ancilla in superposition
h q[0];
// Apply CNOTs (ancilla as control)
cx q[0], q[1];
cx q[0], q[2];
cx q[0], q[3];
cx q[0], q[4];
// Convert back to Z-basis for measurement
h q[0];
// Measure ancilla
measure q[0] -> c[0];

// Reset ancilla for next measurement
reset q[0];

// Second stabilizer measurement (X₁X₂X₅X₆)
// Prepare ancilla in superposition
h q[0];
// Apply CNOTs (ancilla as control)
cx q[0], q[1];
cx q[0], q[2];
cx q[0], q[5];
cx q[0], q[6];
// Convert back to Z-basis for measurement
h q[0];
// Measure ancilla
measure q[0] -> c[1];

// Reset ancilla for next measurement
reset q[0];

// Third stabilizer measurement (X₁X₃X₅X₇)
// Prepare ancilla in superposition
h q[0];
// Apply CNOTs (ancilla as control)
cx q[0], q[1];
cx q[0], q[3];
cx q[0], q[5];
cx q[0], q[7];
// Convert back to Z-basis for measurement
h q[0];
// Measure ancilla
measure q[0] -> c[2];

// Note: This circuit measures the X-stabilizers of the Steane code.
// In a complete implementation, you would also need to measure the
// Z-stabilizers, but they aren't specified in the problem statement.
