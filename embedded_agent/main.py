import time
import sys
import os

# Add current directory to path so imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.actuator import HygienicActuator
from core.ledger import ImmutableLedger
from core.policy_engine import PolicyEngine
from core.visual_cortex import VisualCortex

def main():
    print("==============================================")
    print("   HARDWARE-ISOLATED AGENTIC OPERATOR (HIAO)  ")
    print("   System Starting...                         ")
    print("==============================================")
    
    # 1. Initialize Modules
    try:
        ledger = ImmutableLedger()
        policy = PolicyEngine()
        actuator = HygienicActuator()
        cortex = VisualCortex()
    except Exception as e:
        print(f"CRITICAL: Hardware initialization failed: {e}")
        return

    # 2. Self-Calibration
    print("\n[System] Performing Self-Calibration...")
    # Move mouse to top-left to reset absolute tracking simulation
    actuator.execute_ducky_script("MOUSE_MOVE 0,0")
    time.sleep(1)
    
    start_pos = cortex.locate_cursor()
    ledger.log_action("CALIBRATION", f"Zeroed cursor. Visual confirmation at {start_pos}")
    print("[System] Calibration Complete.")

    # 3. Main Agent Loop
    goal = "Open Terminal"
    print(f"\n[System] Mission Start. Goal: {goal}")
    
    iteration = 0
    max_iterations = 5 # Safety limit for demo

    while iteration < max_iterations:
        iteration += 1
        print(f"\n--- Cycle {iteration} ---")

        try:
            # A. Perception (Look)
            frame_hash = cortex.capture_frame()
            target_coords = cortex.identify_element(goal)
            print(f"[Eye] Found target '{goal}' at {target_coords}")
            
            # B. Reasoning / Action Formulation
            # (In production, an LLM would generate the Ducky Script here)
            script = f"MOUSE_MOVE {target_coords[0]},{target_coords[1]}"
            print(f"[Brain] Generated plan: {script}")
            
            # C. Policy Check (The Conscience)
            is_allowed, reason = policy.validate_command(script)
            
            if is_allowed:
                # D. Execution (The Hands)
                print(f"[Hands] Executing action...")
                actuator.execute_ducky_script(script)
                
                # E. Logging (The Memory)
                ledger.log_action("EXECUTION", script, frame_hash)
                
                # F. Verification
                # Wait for physical action to complete
                time.sleep(1.0) 
                
                # Check if we are closer to the goal (Mock verification)
                current_pos = cortex.locate_cursor()
                # Simple distance check logic would go here
                print(f"[System] Verification: Cursor now at {current_pos}")
                
            else:
                print(f"[Policy] BLOCKED: {reason}")
                ledger.log_action("BLOCKED", script, reason)
                # Simple recovery strategy
                print("[Brain] Re-planning...")
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n[System] Manual Override. Shutting down.")
            break
        except Exception as e:
            print(f"[Error] Unexpected fault: {e}")
            ledger.log_action("ERROR", str(e))
            break

    print("\n[System] Mission Terminated.")

if __name__ == "__main__":
    main()
