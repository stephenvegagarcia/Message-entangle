import socket
import time
import sys
import threading

HOST = '127.0.0.1' 
PORT = 65432        

print(f"TERMINAL//: CONNECTING TO {HOST}:{PORT}")
print("Enter commands to transmit to Grounding Station.")

# Shared flag to kill threads on exit
running = True

def receive_stream(sock):
    """Background thread to handle incoming fidelity data"""
    global running
    while running:
        try:
            data = sock.recv(1024).decode('utf-8')
            if not data:
                print("\n>> DISCONNECTED FROM SOURCE")
                running = False
                break
            
            # Look for FIDELITY data
            lines = data.strip().split('\n')
            for line in lines:
                if "FIDELITY" in line:
                    try:
                        val_str = line.split(':')[1]
                        val = float(val_str)
                        
                        bar_len = 20
                        filled = int(val * bar_len)
                        bar = "█" * filled + "-" * (bar_len - filled)
                        
                        # Print status bar on the current line
                        # Note: This might overlap slightly with typing, which is typical for raw terminals
                        sys.stdout.write(f"\r[LINK ACTIVE] {bar} {val:.4f} | >> ")
                        sys.stdout.flush()
                    except:
                        pass
        except:
            break

try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        print(">> CONNECTION ESTABLISHED. TYPE AND HIT ENTER TO SEND.")
        
        # Start the listener thread
        t = threading.Thread(target=receive_stream, args=(s,))
        t.daemon = True
        t.start()
        
        # Main loop: Waits for USER INPUT to send to the server
        while running:
            user_msg = input() # This blocks waiting for you to type
            if user_msg.lower() == 'exit':
                running = False
                break
            s.sendall(user_msg.encode('utf-8'))
            
except KeyboardInterrupt:
    print("\n>> TERMINATING UPLINK")
except Exception as e:
    print(f"\n>> SYSTEM ERROR: {e}")
