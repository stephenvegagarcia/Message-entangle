import pygame
import numpy as np
import math
import random
import qutip as qt  # Quantum Toolbox in Python

# --- CONFIGURATION ---
WIDTH, HEIGHT = 1000, 700
FPS = 60
BG_COLOR = (5, 5, 10) # Darker for high contrast
HUD_COLOR = (0, 255, 0)
ACCENT_COLOR = (0, 200, 200)
ALERT_COLOR = (255, 50, 80)
HORIZON_COLOR = (255, 215, 0) # Gold for the 2**80 Event

# --- AUDIO ENGINE ---
SAMPLE_RATE = 44100

def generate_sine_wave(freq, duration, volume=0.5):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = np.sin(freq * 2 * np.pi * t)
    audio = (wave * volume * 32767).astype(np.int16)
    return np.column_stack((audio, audio))

def generate_complex_noise(duration):
    # Generates a dense, heavy "computational" noise
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    # Layering multiple frequencies to simulate complexity
    noise = np.sin(50 * 2 * np.pi * t) + np.sin(100 * 2 * np.pi * t) + np.random.uniform(-0.5, 0.5, len(t))
    audio = (noise * 0.1 * 32767).astype(np.int16)
    return np.column_stack((audio, audio))

# --- MAIN APP CLASS ---
class HelloFriendEntropy:
    def __init__(self):
        pygame.init()
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=512)
        
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("SYSTEM//:HORIZON [2**80]")
        self.clock = pygame.time.Clock()
        self.font_main = pygame.font.SysFont("monospace", 18)
        self.font_large = pygame.font.SysFont("monospace", 36)
        self.font_small = pygame.font.SysFont("monospace", 12)
        self.font_micro = pygame.font.SysFont("monospace", 10)

        # STATE
        self.protocol = "INIT: 0"
        self.status_msg = "SYSTEM: IDLE"
        self.access_granted = False
        self.is_scanning = False
        self.scan_timer = 0
        self.entropy_control = 0.1
        self.grounding_level = 0
        self.angle_y = 0.0
        
        # THE MAGIC NUMBER
        self.horizon_limit = 2**80
        self.current_complexity = 0
        
        # QUANTUM STATE
        # We start with a standard qubit. 
        # The 2**80 isn't representable in QuTiP directly (memory overflow), 
        # so we simulate the *result* of that calculation collapsing.
        ket0 = qt.basis(2, 0)
        ket1 = qt.basis(2, 1)
        self.target_state = (qt.tensor(ket0, ket1) - qt.tensor(ket1, ket0)).unit()
        self.current_state = qt.tensor(qt.rand_ket(2), qt.rand_ket(2))
        self.fidelity = 0.0
        
        # VISUAL ASSETS
        self.stars = [(random.randint(0, WIDTH), random.randint(0, 300), random.random()) for _ in range(150)]
        self.matrix_rain = [] # For the 2**80 flood
        
        # AUDIO OBJECTS
        self.sound_sine = pygame.sndarray.make_sound(generate_sine_wave(440, 1.0, 0.3))
        self.sound_horizon = pygame.sndarray.make_sound(generate_sine_wave(55, 1.0, 0.4)) # Low drone
        self.sound_noise = pygame.sndarray.make_sound(generate_complex_noise(1.0))
        
        self.channel_tone = pygame.mixer.Channel(0)
        self.channel_noise = pygame.mixer.Channel(1)
        
        self.channel_noise.play(self.sound_noise, loops=-1)
        self.channel_noise.set_volume(0.8)

    def cycle_protocol(self):
        if self.is_scanning: return

        if self.protocol == "INIT: 0":
            self.protocol = f"HORIZON: 2^{{80}}"
            self.status_msg = "CALCULATING PROBABILITY SPACE..."
        else:
            self.protocol = "INIT: 0"
            self.status_msg = "SYSTEM: IDLE"
            self.current_state = qt.tensor(qt.rand_ket(2), qt.rand_ket(2))
            
        self.is_scanning = True
        self.access_granted = False
        self.scan_timer = 0
        self.entropy_control = 0.1
        self.grounding_level = 0
        self.fidelity = 0.0
        self.current_complexity = 0
        
        self.channel_noise.set_volume(0.8)
        self.channel_tone.set_volume(0.0)

    def update(self):
        self.angle_y += 0.02

        if self.is_scanning:
            self.scan_timer += 1
            
            # SIMULATING THE CLIMB TO 2**80
            if self.protocol == f"HORIZON: 2^{{80}}":
                # Exponential growth simulation
                self.current_complexity = min(self.horizon_limit, 2**(self.scan_timer * 0.8))
                
                # QuTiP Evolution
                if self.scan_timer % 5 == 0:
                    dm_curr = self.current_state.proj() if self.current_state.isket else self.current_state
                    dm_targ = self.target_state.proj()
                    mix = min(1.0, self.scan_timer / 120.0)
                    self.current_state = (1 - mix) * dm_curr + mix * dm_targ
                    self.fidelity = qt.fidelity(self.current_state, self.target_state)
                    self.entropy_control = self.fidelity

            if self.scan_timer > 120:
                self.check_clearance()
                self.is_scanning = False
        
        # Update Matrix Rain for the big event
        if self.grounding_level == 2:
            if len(self.matrix_rain) < 100:
                self.matrix_rain.append([random.randint(0, WIDTH), random.randint(-100, 0), random.randint(5, 15)])
            
            for drop in self.matrix_rain:
                drop[1] += drop[2]
                if drop[1] > HEIGHT:
                    drop[1] = random.randint(-50, 0)
                    drop[0] = random.randint(0, WIDTH)

    def check_clearance(self):
        if self.fidelity > 0.95:
            self.grounding_level = 2
            self.access_granted = True
            self.entropy_control = 1.0
            self.status_msg = "HORIZON REACHED. COLLAPSED."
            self.current_complexity = self.horizon_limit # Snap to max
            
            self.channel_noise.set_volume(0.0)
            self.channel_tone.play(self.sound_sine, loops=-1)
            self.channel_tone.set_volume(0.5)
        else:
            self.grounding_level = 0
            self.access_granted = False
            self.entropy_control = 0.1
            self.status_msg = "COMPUTATIONAL FAILURE"
            self.channel_tone.stop()
            self.channel_noise.set_volume(0.8)

    def draw_top_screen(self, surface, rect):
        pygame.draw.rect(surface, (0, 10, 0), rect)
        pygame.draw.rect(surface, HUD_COLOR, rect, 2)
        
        clip_rect = surface.get_clip()
        surface.set_clip(rect)
        
        # 2**80 VISUALIZATION
        # If Grounded, show the number density
        cx, cy = rect.centerx, rect.centery
        
        if self.grounding_level == 2:
            # Massive centralized sphere of "Data"
            r = 80
            pygame.draw.circle(surface, HORIZON_COLOR, (cx, cy), r, 2)
            pygame.draw.circle(surface, (255, 255, 200), (cx, cy), r-5)
            
            msg = self.font_main.render(f"{self.horizon_limit:,}", True, (0, 0, 0))
            # Center the massive number
            if msg.get_width() > rect.width - 20:
                msg = pygame.transform.scale(msg, (rect.width - 40, msg.get_height()))
            surface.blit(msg, (cx - msg.get_width()//2, cy - msg.get_height()//2))
            
            lbl = self.font_small.render("COMPLEXITY LIMIT REACHED", True, HORIZON_COLOR)
            surface.blit(lbl, (cx - lbl.get_width()//2, cy + 50))
            
        else:
            # Show the climbing number
            disp_num = int(self.current_complexity)
            # Logarithmic bars
            bars = int(math.log(max(1, disp_num), 2))
            
            for i in range(bars):
                bx = rect.x + 20 + (i * 8)
                bh = 5 + (math.sin(i + self.angle_y) * 5)
                # Color shifts from Green to Red as it approaches 80
                c_fac = min(1.0, i / 80.0)
                col = (int(255 * c_fac), int(255 * (1-c_fac)), 100)
                
                if bx < rect.right - 20:
                    pygame.draw.rect(surface, col, (bx, cy - bh, 6, bh*2))
            
            val_txt = f"2^{bars}"
            lbl = self.font_large.render(val_txt, True, HUD_COLOR)
            surface.blit(lbl, (cx - lbl.get_width()//2, cy - lbl.get_height()//2))

        surface.set_clip(clip_rect)
        lbl = self.font_small.render("COMPUTATIONAL_HORIZON", True, (0, 100, 0))
        surface.blit(lbl, (rect.x + 5, rect.y + 5))

    def draw_oscilloscope(self, surface, rect):
        pygame.draw.rect(surface, (0, 0, 0), rect)
        pygame.draw.rect(surface, HUD_COLOR, rect, 2)
        cx, cy = rect.centerx, rect.centery

        # Matrix Rain Effect in background for 2**80
        if self.grounding_level == 2:
            for drop in self.matrix_rain:
                if rect.collidepoint(drop[0], rect.y + 10): # Simple containment check
                     txt = self.font_micro.render(str(random.randint(0,1)), True, (0, 100, 0))
                     surface.blit(txt, (drop[0], rect.y + (drop[1] % rect.height)))

            # Pure Signal
            points = []
            for x in range(rect.x, rect.right, 2):
                nx = (x - rect.x) / rect.width
                y = cy + math.sin(nx * 50 + self.angle_y * 20) * 40
                points.append((x, y))
            if len(points) > 1:
                pygame.draw.lines(surface, HORIZON_COLOR, False, points, 2)
                
            msg = self.font_large.render("HELLO FRIEND", True, HUD_COLOR)
            surface.blit(msg, (cx - msg.get_width()//2, cy - msg.get_height()//2))
            
        else:
            # Chaos Noise
            points = []
            for x in range(rect.x, rect.right, 2):
                nx = (x - rect.x) / rect.width
                # Amplitude based on how close we are to 80
                amp = 30 + (math.log(max(1, self.current_complexity), 2) / 2)
                y = cy + math.sin(nx * 100 + self.angle_y*5) * amp * random.random()
                points.append((x, y))
            if len(points) > 1:
                pygame.draw.lines(surface, (50, 50, 50), False, points, 1)
            
            stat = self.font_main.render(f"PROCESSING: {int(self.current_complexity):.1e}", True, HUD_COLOR)
            surface.blit(stat, (cx - stat.get_width()//2, cy))

        lbl = self.font_small.render("SIGNAL::ENTROPY_DENSITY", True, (0, 100, 0))
        surface.blit(lbl, (rect.x + 5, rect.y + 5))

    def draw_bloch_sphere(self, surface, rect):
        pygame.draw.rect(surface, (10, 15, 25), rect)
        pygame.draw.rect(surface, HUD_COLOR, rect, 1)
        
        cx, cy = rect.centerx, rect.centery
        r = 80
        
        pygame.draw.circle(surface, ACCENT_COLOR, (cx, cy), r, 1)
        pygame.draw.ellipse(surface, ACCENT_COLOR, (cx-r, cy-r//3, r*2, r*0.66), 1)

        if self.grounding_level == 2:
            # The Golden Vector (2**80 state)
            v1 = (cx, cy - r) # Pointing Up
            v2 = (cx, cy + r) # Pointing Down
            
            # Draw a dense beam connecting them
            pygame.draw.line(surface, HORIZON_COLOR, v1, v2, 4)
            
            # Orbital rings representing density
            pygame.draw.ellipse(surface, HORIZON_COLOR, (cx-r//2, cy-r, r, r*2), 1)
            
            lbl = self.font_small.render("∞ COLLAPSED", True, HORIZON_COLOR)
            surface.blit(lbl, (cx - lbl.get_width()//2, cy - 10))
            
        else:
            # Cloud of points representing the search space
            count = int(math.log(max(2, self.current_complexity), 2)) * 2
            for i in range(min(count, 100)):
                rx = cx + random.randint(-r, r)
                ry = cy + random.randint(-r, r)
                # Check coords inside circle
                if math.hypot(rx-cx, ry-cy) < r:
                    pygame.draw.circle(surface, (0, 255, 255), (rx, ry), 1)

            lbl = self.font_small.render("SEARCHING HILBERT SPACE", True, (100, 100, 100))
            surface.blit(lbl, (cx - lbl.get_width()//2, cy + r + 10))

        lbl = self.font_small.render("QUANTUM_STATE", True, ACCENT_COLOR)
        surface.blit(lbl, (rect.x + 5, rect.y + 5))

    def run(self):
        running = True
        
        rect_top = pygame.Rect(20, 80, 600, 250)
        rect_bot = pygame.Rect(20, 350, 600, 250)
        rect_side = pygame.Rect(640, 80, 340, 300)
        rect_btn = pygame.Rect(640, 400, 340, 100)

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if rect_btn.collidepoint(event.pos):
                        self.cycle_protocol()

            self.update()
            self.screen.fill(BG_COLOR)
            
            head = self.font_large.render("SYSTEM//:HORIZON_LIMIT", True, HUD_COLOR)
            self.screen.blit(head, (20, 20))
            
            self.draw_top_screen(self.screen, rect_top)
            self.draw_oscilloscope(self.screen, rect_bot)
            self.draw_bloch_sphere(self.screen, rect_side)
            
            pygame.draw.rect(self.screen, (20, 30, 40), rect_btn)
            border_col = HUD_COLOR if not self.is_scanning else (100, 100, 100)
            pygame.draw.rect(self.screen, border_col, rect_btn, 2)
            
            status = self.font_main.render(self.protocol, True, ACCENT_COLOR)
            self.screen.blit(status, (rect_btn.x + 10, rect_btn.y + 10))
            
            sub_status = self.font_small.render(self.status_msg, True, HORIZON_COLOR if self.grounding_level == 2 else ALERT_COLOR)
            self.screen.blit(sub_status, (rect_btn.x + 10, rect_btn.y + 40))
            
            btn_lbl = "CALCULATING..." if self.is_scanning else f"INITIATE 2^80"
            btn_txt = self.font_main.render(btn_lbl, True, HUD_COLOR)
            self.screen.blit(btn_txt, (rect_btn.centerx - btn_txt.get_width()//2, rect_btn.bottom - 30))

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()

if __name__ == "__main__":
    app = HelloFriendEntropy()
    app.run()
