import state_manager as state
import os

print(f"State file path: {state.STATE_FILE}")
state.save_shared_state(state.SHARED_DATA)
if os.path.exists(state.STATE_FILE):
    print("SUCCESS: File created.")
else:
    print("FAILURE: File not created.")
