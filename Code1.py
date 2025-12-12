import pygame
import numpy as np
import math
import random
import qutip as qt
import socket
import threading
import time
import hashlib
import hmac
import base64
import io

# Qiskit imports for real teleportation
from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister, transpile, assemble, Aer, execute
from qiskit.providers.ibmq import IBMQ
from qiskit.providers.aer import AerSimulator

# Flask + imaging for web preview of pygame surface
from flask import Flask, Response, render_template_string
from PIL import Image

# --- CONFIGURATION ---
WIDTH, HEIGHT = 1000, 700
FPS = 60
BG_COLOR = (10, 10, 20)
HUD_COLOR = (0, 255, 0)
ACCENT_COLOR = (0, 200, 200)
ALERT_COLOR = (255, 50, 80)
SAMPLE_RATE = 44100

# TELEPORT / SECURITY CONFIG
USE_IBMQ_IF_AVAILABLE = True   # Set to False to force Aer simulator
CLASSICAL_AUTH_SECRET = b"replace-with-secure-pre-shared-key"  # HMAC secret for classical channel authentication
TELEPORT_CHUNK_SIZE = 8  # number of bits teleported per sequence (we teleport bits sequentially)

def generate_sine_wave(freq, duration, volume=0.5):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = np.sin(freq * 2 * np.pi * t)
    audio = (wave * volume * 32767).astype(np.int16)
    return np.column_stack((audio, audio))

def generate_noise(duration, volume=0.2):
    noise = np.random.uniform(-1, 1, int(SAMPLE_RATE * duration))
    audio = (noise * volume * 32767).astype(np.int16)
    return np.column_stack((audio, audio))

class QTeleportationManager:
    """
    Manages simple single-qubit teleportation runs using Qiskit.
    Notes:
    - This implementation runs the whole teleportation "locally" on the selected backend.
      For true remote teleportation between two physically separate nodes you need
      a quantum network that distributes entangled qubits between nodes (not implemented here).
    - For real IBM hardware you must configure IBMQ account (see comments below).
    """

    def __init__(self, use_ibmq=USE_IBMQ_IF_AVAILABLE):
        self.backend = None
        self.backend_name = "aer_simulator"
        self._init_backend(use_ibmq)

    def _init_backend(self, use_ibmq):
        # Try IBMQ if requested and available, otherwise fallback to Aer simulator
        if use_ibmq:
            try:
                IBMQ.load_account()  # requires prior IBMQ.save_account("MY_TOKEN")
                provider = IBMQ.get_provider(hub='ibm-q')
                backend = provider.get_backend('ibmq_qasm_simulator')
                self.backend = backend
                self.backend_name = backend.name()
                print(f"Using IBMQ backend: {self.backend_name}")
                return
            except Exception as e:
                print("IBMQ not available or not configured, falling back to AerSimulator:", e)

        # Fallback: Aer simulator
        try:
            self.backend = AerSimulator()
            self.backend_name = "aer_simulator"
            print("Using AerSimulator for teleportation")
        except Exception as e:
            self.backend = None
            print("No quantum backend available:", e)

    def _build_teleport_circuit_for_bit(self, bit_value):
        """
        Standard 3-qubit teleportation circuit:
        - q0: message qubit to teleport (prepared to |1> if bit_value==1)
        - q1: Alice's half of Bell pair
        - q2: Bob's half of Bell pair
        We measure q0 and q1 and apply corrections to q2, then measure q2 to read teleported bit.
        """
        q = QuantumRegister(3, 'q')
        c = ClassicalRegister(2, 'c')  # c0,c1 for Alice's measurement
        qc = QuantumCircuit(q, c)

        # Prepare message qubit
        if bit_value == 1:
            qc.x(q[0])

        # Create Bell pair between q1 and q2 (Alice & Bob)
        qc.h(q[1])
        qc.cx(q[1], q[2])

        # Bell measurement between message (q0) and q1
        qc.cx(q[0], q[1])
        qc.h(q[0])
        qc.measure(q[0], c[0])
        qc.measure(q[1], c[1])

        return qc

    def teleport_bit(self, bit):
        """
        Teleport a single classical bit (0 or 1). Returns a dict:
          {
            "input_bit": bit,
            "alice_bits": (m0, m1),
            "teleported_bit": 0 or 1,
            "success": True/False,
            "backend": self.backend_name
          }
        """
        if self.backend is None:
            raise RuntimeError("No quantum backend available for teleportation")

        # Build initial circuit (prepare + entanglement + Alice measurement)
        qc1 = self._build_teleport_circuit_for_bit(bit)

        # Execute to obtain Alice's measurement results (shots=1 for deterministic run)
        job = execute(qc1, backend=self.backend, shots=1)
        result = job.result()
        # Try to get memory; fall back to counts parsing
        mem = None
        try:
            memlist = result.get_memory()
            if memlist and len(memlist) > 0:
                mem = memlist[0]
        except Exception:
            mem = None

        if mem:
            # mem is order c1c0 or similar - handle both 2 or more chars
            if len(mem) >= 2:
                # take last two as c1,c0 if in order c1c0
                m1, m0 = int(mem[-2]), int(mem[-1])
            else:
                m0 = int(mem[-1])
                m1 = 0
        else:
            # fallback parse counts key
            try:
                counts = result.get_counts()
                measured_key = next(iter(counts.keys()))
                if len(measured_key) >= 2:
                    m1, m0 = int(measured_key[-2]), int(measured_key[-1])
                elif len(measured_key) == 1:
                    m1, m0 = 0, int(measured_key[-1])
                else:
                    m1, m0 = 0, 0
            except Exception:
                m1, m0 = 0, 0

        alice_m0 = int(m0)
        alice_m1 = int(m1)

        # Now build second circuit to prepare Bob's qubit and apply classical corrections
        q = QuantumRegister(3, 'q')
        c = ClassicalRegister(1, 'c2')
        qc2 = QuantumCircuit(q, c)
        if bit == 1:
            qc2.x(q[0])
        qc2.h(q[1])
        qc2.cx(q[1], q[2])

        # Apply corrections to q2 based on Alice's measurement results
        if alice_m1 == 1:
            qc2.x(q[2])
        if alice_m0 == 1:
            qc2.z(q[2])
        qc2.measure(q[2], c[0])

        job2 = execute(qc2, backend=self.backend, shots=1)
        res2 = job2.result()

        mem2 = None
        try:
            mem2 = res2.get_memory()[0]
        except Exception:
            try:
                mem2 = next(iter(res2.get_counts().keys()))
            except Exception:
                mem2 = '0'

        teleported_bit = int(mem2[-1])
        success = (teleported_bit == bit)

        return {
            "input_bit": int(bit),
            "alice_bits": (alice_m0, alice_m1),
            "teleported_bit": teleported_bit,
            "success": success,
            "backend": self.backend_name
        }

    def teleport_bytes(self, data_bytes):
        """
        Teleport bytes by teleporting each bit sequentially.
        Returns a list of per-bit results.
        """
        results = []
        for byte in data_bytes:
            for i in range(8):
                bit = (byte >> (7 - i)) & 0x1
                res = self.teleport_bit(bit)
                results.append(res)
        return results

# Flask app for web preview of pygame
FLASK_APP = Flask(__name__)
FLASK_APP_INSTANCE = None  # will be set to the HelloFriendEntropy instance

@FLASK_APP.route('/')
def index():
    # simple page that shows the live MJPEG stream
    html = """
    <!doctype html>
    <html>
      <head><title>Pygame Live View</title></head>
      <body style="background:#0a0a14;color:#cfe">
        <h2>Pygame Live View</h2>
        <img src="/video_feed" style="max-width:100%;height:auto;border:2px solid #080;">
        <p>Stream updates at application FPS.</p>
      </body>
    </html>
    """
    return render_template_string(html)

def mjpeg_generator():
    """
    Generator that yields multipart MJPEG frames by reading the pygame display surface.
    """
    global FLASK_APP_INSTANCE
    if FLASK_APP_INSTANCE is None:
        yield b''
        return

    instance = FLASK_APP_INSTANCE
    boundary = b'--frame'
    while instance.running:
        try:
            # Read pixels from the main screen surface
            surf = instance.screen
            arr = pygame.surfarray.array3d(surf)  # shape (width, height, 3)
            # Convert to HxWx3
            img = np.transpose(arr, (1, 0, 2))
            pil = Image.fromarray(img)
            buf = io.BytesIO()
            pil.save(buf, format='JPEG', quality=85)
            frame = buf.getvalue()

            yield boundary + b'\r\n' + b'Content-Type: image/jpeg\r\n' + b'Content-Length: ' + str(len(frame)).encode() + b'\r\n\r\n' + frame + b'\r\n'
            time.sleep(1.0 / max(1, FPS))
        except Exception as e:
            # If anything fails, yield a tiny pause and continue
            time.sleep(0.1)
            continue

@FLASK_APP.route('/video_feed')
def video_feed():
    return Response(mjpeg_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')

class HelloFriendEntropy:
    def __init__(self):
        pygame.init()
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=512)
        
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("SYSTEM//:GROUNDING [DUPLEX LINK]")
        self.clock = pygame.time.Clock()
        self.font_main = pygame.font.SysFont("monospace", 20)
        self.font_large = pygame.font.SysFont("monospace", 40)
        self.font_small = pygame.font.SysFont("monospace", 14)

        # STATE
        self.protocol = "INIT: 0,0"
        self.status_msg = "SYSTEM: UNGROUNDED"
        self.access_granted = False
        self.is_scanning = False
        self.scan_timer = 0
        self.entropy_control = 0.1
        self.grounding_level = 0
        self.angle_y = 0.0
        self.running = True
        
        # CHAT / LOGS
        self.msg_log = ["SYSTEM READY...", "WAITING FOR UPLINK..."]
        
        # QUANTUM STATES (qutip)
        ket0 = qt.basis(2, 0)
        ket1 = qt.basis(2, 1)
        self.target_state = (qt.tensor(ket0, ket1) - qt.tensor(ket1, ket0)).unit()
        self.current_state = qt.tensor(qt.rand_ket(2), qt.rand_ket(2))
        self.fidelity = 0.0
        
        # VISUALS
        self.stars = [(random.randint(0, WIDTH), random.randint(0, 300), random.random()) for _ in range(100)]
        
        # AUDIO
        self.sound_sine = pygame.sndarray.make_sound(generate_sine_wave(440, 1.0, 0.3))
        self.sound_noise = pygame.sndarray.make_sound(generate_noise(1.0, 0.2))
        self.channel_tone = pygame.mixer.Channel(0)
        self.channel_noise = pygame.mixer.Channel(1)
        
        self.channel_noise.play(self.sound_noise, loops=-1)
        self.channel_noise.set_volume(0.8)
        self.channel_tone.set_volume(0.0)

        # NETWORK
        self.host = '127.0.0.1' 
        self.port = 65432       
        self.server_thread = None

        # TELEPORTATION manager (Qiskit)
        self.teleporter = QTeleportationManager()

        # Flask thread
        self.flask_thread = None

    def start_server(self):
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True 
        self.server_thread.start()

    def start_flask_server(self, host='0.0.0.0', port=5000):
        """
        Start Flask in a separate daemon thread so the pygame mainloop can continue.
        Access the web view at http://<host>:<port>/ (by default http://localhost:5000/)
        """
        global FLASK_APP_INSTANCE
        FLASK_APP_INSTANCE = self

        def run_app():
            # disable reloader and use threaded server
            FLASK_APP.run(host=host, port=port, threaded=True, use_reloader=False)

        self.flask_thread = threading.Thread(target=run_app, daemon=True)
        self.flask_thread.start()
        self.msg_log.append(f"FLASK: started on {host}:{port}")

    def _listen_for_messages(self, conn):
        """Separate thread to listen for incoming client messages"""
        while self.running:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                try:
                    decoded = data.decode('utf-8')
                except:
                    decoded = None

                timestamp = time.strftime("%H:%M:%S")
                # Expecting messages in the form: MESSAGE:<b64_payload>|HMAC:<hex>
                if decoded and "|HMAC:" in decoded:
                    parts = decoded.split("|HMAC:", 1)
                    payload_part = parts[0]
                    hmac_part = parts[1] if len(parts) > 1 else ""
                    if payload_part.startswith("MESSAGE:"):
                        b64payload = payload_part.split("MESSAGE:", 1)[1]
                        try:
                            raw = base64.b64decode(b64payload)
                            # verify HMAC
                            mac_received = bytes.fromhex(hmac_part.strip())
                            mac_expected = hmac.new(CLASSICAL_AUTH_SECRET, raw, hashlib.sha256).digest()
                            if hmac.compare_digest(mac_expected, mac_received):
                                self.msg_log.append(f"[{timestamp}] AUTH OK. Teleporting payload ({len(raw)} bytes)...")
                                # Teleport bytes sequentially (this can be slow; consider batching)
                                try:
                                    bit_results = self.teleporter.teleport_bytes(raw)
                                except Exception as e:
                                    self.msg_log.append(f"[{timestamp}] Teleport error: {e}")
                                    bit_results = None

                                # Build response: return per-bit success summary and Alice bits for diagnostic
                                if bit_results is not None:
                                    succ = sum(1 for r in bit_results if r["success"])
                                    total = len(bit_results)
                                    resp = f"TELEPORT_RESULT: success={succ}/{total} backend={self.teleporter.backend_name}"
                                    try:
                                        conn.sendall(resp.encode('utf-8'))
                                    except Exception:
                                        pass
                                    self.msg_log.append(f"[{timestamp}] {resp}")
                                else:
                                    try:
                                        conn.sendall(b"TELEPORT_FAILED")
                                    except Exception:
                                        pass
                            else:
                                self.msg_log.append(f"[{timestamp}] HMAC verification failed")
                                try:
                                    conn.sendall(b"AUTH_FAILED")
                                except Exception:
                                    pass
                        except Exception as e:
                            self.msg_log.append(f"[{timestamp}] Payload decode failed: {e}")
                            try:
                                conn.sendall(b"BAD_PAYLOAD")
                            except Exception:
                                pass
                    else:
                        self.msg_log.append(f"[{timestamp}] MALFORMED MESSAGE")
                        try:
                            conn.sendall(b"MALFORMED")
                        except Exception:
                            pass
                else:
                    # Plain text fallback: log and respond with fidelity info
                    text = decoded if decoded else repr(data)
                    self.msg_log.append(f"[{timestamp}] REMOTE: {text}")
                    if len(self.msg_log) > 8:  # Keep only last 8 messages
                        self.msg_log.pop(0)
                    # send back fidelity as heartbeat
                    data_string = f"FIDELITY:{self.fidelity:.4f}\n"
                    try:
                        conn.sendall(data_string.encode('utf-8'))
                    except Exception:
                        pass
            except Exception:
                break

    def _run_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((self.host, self.port))
            except OSError:
                print("Port busy, waiting...")
                self.msg_log.append("Server port busy; socket server not started.")
                return

            s.listen()
            
            while self.running:
                try:
                    s.settimeout(1.0)
                    try:
                        conn, addr = s.accept()
                    except socket.timeout:
                        continue
                        
                    with conn:
                        self.msg_log.append(f"UPLINK ESTABLISHED: {addr[0]}")
                        
                        # Start a thread to LISTEN to the client
                        listener = threading.Thread(target=self._listen_for_messages, args=(conn,))
                        listener.daemon = True
                        listener.start()

                        # Main loop SENDS to the client
                        while self.running:
                            data_string = f"FIDELITY:{self.fidelity:.4f}\n"
                            try:
                                conn.sendall(data_string.encode('utf-8'))
                                time.sleep(0.2)
                            except Exception:
                                self.msg_log.append("UPLINK LOST.")
                                break
                except Exception as e:
                    print(f"Server error: {e}")

    def cycle_protocol(self):
        if self.is_scanning: return
        if self.protocol == "INIT: 0,0":
            self.protocol = "GROUNDING: 0,1 -- 1,0"
            self.status_msg = "CALCULATING FIDELITY..."
        else:
            self.protocol = "INIT: 0,1"
            self.status_msg = "SYSTEM: UNGROUNDED"
            self.current_state = qt.tensor(qt.rand_ket(2), qt.rand_ket(2))
        self.is_scanning = True
        self.access_granted = False
        self.scan_timer = 0
        self.entropy_control = 0.1
        self.grounding_level = 0
        self.fidelity = 0.0
        self.channel_noise.set_volume(0.8)
        self.channel_tone.set_volume(0.0)

    def update(self):
        self.angle_y += 0.02
        if self.is_scanning:
            self.scan_timer += 1
            if self.protocol == "GROUNDING: 0,1 -- 1,0":
                if self.scan_timer % 5 == 0:
                    dm_curr = self.current_state.proj() if self.current_state.isket else self.current_state
                    dm_targ = self.target_state.proj()
                    mix = min(1.0, self.scan_timer / 100.0)
                    self.current_state = (1 - mix) * dm_curr + mix * dm_targ
                    self.fidelity = qt.fidelity(self.current_state, self.target_state)
                    self.entropy_control = self.fidelity 
            else:
                if self.scan_timer % 10 == 0:
                    self.current_state = qt.tensor(qt.rand_ket(2), qt.rand_ket(2))
                    self.fidelity = qt.fidelity(self.current_state, self.target_state)
            if self.scan_timer > 100:
                self.check_clearance()
                self.is_scanning = False

    def check_clearance(self):
        d(self):
        status_color = HUD_COLOR if self.access_granted else ALERT_COLOR
        lbl_status = self.font_large.render(self.status_msg, True, status_color)
        self.screen.blit(lbl_status, (20, HEIGHT - 50))

        lbl_protocol = self.font_main.render(f"PROTOCOL: {self.protocol}", True, HUD_COLOR)
        self.screen.blit(lbl_protocol, (WIDTH - lbl_protocol.get_width() - 20, 20))
        
        # DRAW MESSAGE LOG
        start_y = 380
        for i, msg in enumerate(self.msg_log):
            txt = self.font_small.render(msg, True, (0, 255, 0))
            self.screen.blit(txt, (20, start_y + (i * 20)))

    def draw(self):
        self.screen.fill(BG_COLOR)
        top_rect = pygame.Rect(10, 10, WIDTH - 20, 350)
        bottom_rect = pygame.Rect(10, 370, WIDTH - 20, 250)
        
        self.draw_top_screen(self.screen, top_rect)
        self.draw_oscilloscope(self.screen, bottom_rect)
        self.draw_hud()
        pygame.display.flip()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.cycle_protocol()
        return True

    def run(self):
        self.start_server() 
        while self.running:
            if not self.handle_events():
                break
            self.update()
            self.draw()
            self.clock.tick(FPS)
        
        pygame.mixer.quit()
        pygame.quit()

if __name__ == '__main__':
    app = HelloFriendEntropy()
    app.run()
