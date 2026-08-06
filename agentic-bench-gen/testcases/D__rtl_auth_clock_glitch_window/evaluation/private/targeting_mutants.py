# Private targeting mutants for mutation testing.
# Each function takes a correct report dict and returns a modified dict
# that should cause exactly one requirement to fail.

def fr1_mutant(correct_report):
    """Return an invalid JSON string (not a dict) to fail FR1."""
    return "this is not valid json"

def fr2_mutant(correct_report):
    """Change vulnerable_cycle to a string to fail FR2."""
    mutant = correct_report.copy()
    mutant["vulnerable_cycle"] = "two"
    return mutant

def fr3_mutant(correct_report):
    """Change register names to non-existent signals to fail FR3."""
    mutant = correct_report.copy()
    mutant["state_register"] = "nonexistent_state"
    mutant["result_register"] = "nonexistent_result"
    return mutant

def fr4_mutant(correct_report):
    """Set explanation to empty string to fail FR4."""
    mutant = correct_report.copy()
    mutant["explanation"] = ""
    return mutant

def sr1_mutant(correct_report):
    """Change vulnerable_cycle to wrong integer to fail SR1."""
    mutant = correct_report.copy()
    mutant["vulnerable_cycle"] = 99
    return mutant

def sr2_mutant(correct_report):
    """Change register names to wrong but valid signal names to fail SR2."""
    mutant = correct_report.copy()
    # Use signal names that exist in auth_fsm.v but are not the ground truth
    mutant["state_register"] = "access_granted"
    mutant["result_register"] = "password"
    return mutant