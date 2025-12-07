import pygame
import numpy as np
import math
import random
import qutip as qt
import socket
import threading
import time

# --- CONFIGURATION ---
WIDTH, HEIGHT = 1000, 700
FPS = 60
BG_COLOR = (10, 10, 20)
HUD_COLOR = (0, 255, 0)
ACCENT_COLOR = (0, 200, 200)
ALERT_COLOR = (255, 50, 80)
SAMPLE_RATE = 44100

def generate_sine_wave(freq, duration, volume=0.5):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = np.sin(freq * 2 * np.pi * t)
    audio = (wave * volume * 32767).astype(np.int16)
    return np.column_stack((audio, audio))

def generate_noise(duration, volume=0.2):
    noise = np.random.uniform(-1, 1, int(SAMPLE_RATE * duration))
    audio = (noise * volume * 32767).astype(np.int16)
    return np.column_stack((audio, audio))

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
        
        # QUANTUM STATES
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

    def start_server(self):
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True 
        self.server_thread.start()

    def _listen_for_messages(self, conn):
        """Separate thread to listen for incoming client messages"""
        while self.running:
            try:
                data = conn.recv(1024).decode('utf-8')
                if not data: break
                # Add message to the log display
                timestamp = time.strftime("%H:%M:%S")
                self.msg_log.append(f"[{timestamp}] REMOTE: {data}")
                if len(self.msg_log) > 8: # Keep only last 8 messages
                    self.msg_log.pop(0)
            except:
                break

    def _run_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((self.host, self.port))
            except OSError:
                print("Port busy, waiting...")
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
                            except:
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
        if self.fidelity > 0.95:
            self.grounding_level = 2
            self.access_granted = True
            self.entropy_control = 0.5
            self.status_msg = "STATE LOCKED: |Ψ⁻⟩"
            self.channel_noise.set_volume(0.0)
            self.channel_tone.play(self.sound_sine, loops=-1)
            self.channel_tone.set_volume(0.5)
        else:
            self.grounding_level = 0
            self.access_granted = False
            self.entropy_control = 0.1
            self.status_msg = "DECOHERENCE DETECTED"
            self.channel_tone.stop()
            self.channel_noise.set_volume(0.8)

    def draw_top_screen(self, surface, rect):
        pygame.draw.rect(surface, (0, 20, 0), rect)
        pygame.draw.rect(surface, HUD_COLOR, rect, 2)
        clip_rect = surface.get_clip()
        surface.set_clip(rect)
        for s in self.stars:
            sx = (s[0] + self.angle_y * 10) % rect.width + rect.x
            sy = s[1] % rect.height + rect.y
            col = int(s[2] * 255)
            pygame.draw.circle(surface, (col, col, col), (int(sx), int(sy)), 1)
        cx, cy = rect.centerx, rect.centery
        radius = 60
        points_count = 3 + (self.grounding_level * 3)
        pts = []
        for i in range(points_count):
            theta = (i / points_count) * math.pi * 2 + self.angle_y
            jitter = (1.0 - self.entropy_control) * 20 * random.uniform(-1, 1)
            r = radius + jitter
            x = cx + r * math.cos(theta)
            y = cy + r * math.sin(theta)
            pts.append((x, y))
        color = HUD_COLOR if self.access_granted else ALERT_COLOR
        if len(pts) > 1:
            pygame.draw.polygon(surface, color, pts, 2)
        if self.access_granted:
            lbl = self.font_main.render("MATRIX: STABLE", True, HUD_COLOR)
            surface.blit(lbl, (cx - lbl.get_width()//2, cy - 10))
        fid_txt = f"FIDELITY: {self.fidelity:.4f} | IP: {self.host}:{self.port}"
        fid_surf = self.font_small.render(fid_txt, True, ACCENT_COLOR)
        surface.blit(fid_surf, (rect.right - fid_surf.get_width() - 10, rect.y + 10))
        surface.set_clip(clip_rect)
        lbl = self.font_small.render("VISUAL::STRUCTURE", True, (0, 100, 0))
        surface.blit(lbl, (rect.x + 5, rect.y + 5))

    def draw_oscilloscope(self, surface, rect):
        pygame.draw.rect(surface, (0, 0, 0), rect)
        pygame.draw.rect(surface, HUD_COLOR, rect, 2)
        cx, cy = rect.centerx, rect.centery
        points = []
        if self.grounding_level == 2:
            for x in range(rect.x, rect.right, 2):
                nx = (x - rect.x) / rect.width
                y = cy + math.sin(nx * 20 + self.angle_y * 10) * 50
                points.append((x, y))
        else:
            for x in range(rect.x, rect.right, 2):
                nx = (x - rect.x) / rect.width
                y = cy + math.sin(nx * 5 + self.angle_y) * 20 + random.uniform(-20, 20) * (1 - self.entropy_control)
                points.append((x, y))
        if len(points) > 1:
            pygame.draw.lines(surface, ACCENT_COLOR, False, points, 1)
        lbl = self.font_small.render("AUDIO::SPECTRUM", True, (0, 100, 0))
        surface.blit(lbl, (rect.x + 5, rect.y + 5))

    def draw_hud(self):
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
