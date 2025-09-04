from vpython import *
import math
import time

# ---------- Configuração de cena global ----------
scene.title = "Sistema Solar Interativo 3D"
scene.width = 1280
scene.height = 720
scene.background = color.black
scene.forward = vector(-1, -0.2, -1)

# Luz solar
sun_light = local_light(pos=vector(0,0,0), color=color.white)

# ---------- Parâmetros de Simulação ----------
TIME_SCALE = 5000.0  
PAUSED = False
SHOW_ORBITS = True
SHOW_LABELS = True
SHOW_TRAILS = True
INFO_VISIBLE = True
AUTO_ROTATE = False
ROTATION_SPEED = 0.1

# Fatores de escala visual (arbitrários, para visibilidade)
RADIUS_SCALE = 0.0005     
DIST_SCALE   = 0.0000015  

# ---------- Definições de Dados ----------
# Conjunto básico de planetas com valores médios aproximados
# Distâncias: semieixo maior (km); Raios: raio equatorial (km); Períodos: dias/horas
bodies_config = [
    {
        "name":"Mercúrio", "radius_km":2439.7, "color":color.gray(0.7),
        "distance_km":57_909_050, "orbital_period_days":87.969, "rotation_period_hours":1407.6,
        "tilt_deg":0.03, "texture":None, "has_rings":False
    },
    {
        "name":"Vênus", "radius_km":6051.8, "color":color.orange,
        "distance_km":108_209_475, "orbital_period_days":224.701, "rotation_period_hours":-5832.5,  
        "tilt_deg":177.4, "texture":None, "has_rings":False
    },
    {
        "name":"Terra", "radius_km":6378.1, "color":color.white,
        "distance_km":149_598_262, "orbital_period_days":365.256, "rotation_period_hours":23.934,
        "tilt_deg":23.44, "texture":textures.earth, "has_rings":False
    },
    {
        "name":"Marte", "radius_km":3396.2, "color":color.red,
        "distance_km":227_943_824, "orbital_period_days":686.980, "rotation_period_hours":24.623,
        "tilt_deg":25.19, "texture":None, "has_rings":False
    },
    {
        "name":"Júpiter", "radius_km":71492, "color":color.white,
        "distance_km":778_340_821, "orbital_period_days":4332.59, "rotation_period_hours":9.925,
        "tilt_deg":3.13, "texture":None, "has_rings":False
    },
    {
        "name":"Saturno", "radius_km":60268, "color":color.yellow,
        "distance_km":1_426_666_422, "orbital_period_days":10_759.22, "rotation_period_hours":10.7,
        "tilt_deg":26.73, "texture":None, "has_rings":True
    },
    {
        "name":"Urano", "radius_km":40895, "color":color.cyan,
        "distance_km":2_870_658_186, "orbital_period_days":30_688.5, "rotation_period_hours":-17.24,
        "tilt_deg":97.77, "texture":None, "has_rings":True
    },
    {
        "name":"Netuno", "radius_km":39623, "color":color.blue,
        "distance_km":4_498_396_441, "orbital_period_days":60_182, "rotation_period_hours":16.11,
        "tilt_deg":28.32, "texture":None, "has_rings":True
    }
]

# Lua para a Terra (bruto)
moon_config = {
    "name":"Lua", "radius_km":1737.4, "color":color.gray(0.8),
    "distance_km":384_400, "orbital_period_days":27.321661, "rotation_period_hours":655.7,
    "tilt_deg":6.68
}

# ---------- Classes ----------
class Planet:
    def __init__(self, cfg, sun_obj):
        self.name = cfg["name"]
        self.R = cfg["radius_km"] * RADIUS_SCALE
        self.a = cfg["distance_km"] * DIST_SCALE  
        self.T = cfg["orbital_period_days"] * 24 * 3600  
        self.rotT = abs(cfg["rotation_period_hours"]) * 3600 if cfg["rotation_period_hours"] != 0 else 1
        self.retrograde = cfg["rotation_period_hours"] < 0
        self.tilt = math.radians(cfg["tilt_deg"])
        self.has_rings = cfg.get("has_rings", False)
        tex = cfg.get("texture", None)
        col = cfg.get("color", color.white)

        # Criar esfera 3D
        self.body = sphere(
            pos=vector(self.a, 0, 0),
            radius=self.R,
            color=col if tex is None else color.white,
            make_trail=False,
            shininess=0.8,
            emissive=False,
            texture=tex
        )
        # Visualização da inclinação do eixo (sutil)
        axis_len = self.R * 1.5
        self.axis_line = curve(pos=[self.body.pos - vector(0, math.sin(self.tilt)*self.R, 0),
                                    self.body.pos + vector(0, math.sin(self.tilt)*self.R, 0)],
                               radius=self.R*0.02, color=col)

        if SHOW_TRAILS:
            self.body.make_trail = True
            self.body.retain = 500

        # Anel de órbita (no plano XY para simplificar)
        self.orbit = ring(pos=vector(0,0,0), axis=vector(0,1,0),
                          radius=self.a, thickness=self.a*0.002,
                          color=color.gray(0.3), visible=SHOW_ORBITS)

        # Anéis opcionais (Saturno, Urano, Netuno)
        self.rings = None
        if self.has_rings:
            ring_color = color.gray(0.7)
            if self.name == "Uranus":
                ring_color = color.cyan
            elif self.name == "Neptune":
                ring_color = color.blue
                
            self.rings = ring(pos=self.body.pos, axis=vector(0, math.cos(self.tilt), 0),
                              radius=self.R*2.2, thickness=self.R*0.15,
                              color=ring_color)

        # Label
        self.lbl = label(pos=self.body.pos, text=self.name, xoffset=0, yoffset=40,
                         height=12, color=color.white, box=False, opacity=0,
                         visible=SHOW_LABELS, space=30)

        # Ângulos
        self.theta = 0.0  # ângulo orbital
        self.spin = 0.0   # ângulo de rotação

        # Parent: Sol
        self.sun = sun_obj

        # Lua container
        self.moons = []

    def add_moon(self, moon_cfg):
        m = Moon(moon_cfg, self)
        self.moons.append(m)
        return m

    def update(self, dt):
        # Update posição orbital (movimento circular uniforme)
        if self.T > 0:
            self.theta = (self.theta + (2*math.pi/TIME_SAFE(self.T))*dt) % (2*math.pi)
        self.body.pos = vector(self.a*math.cos(self.theta), 0, self.a*math.sin(self.theta))

        # Rotação própria
        if self.rotT > 0:
            sgn = -1 if self.retrograde else 1
            self.spin = (self.spin + sgn*(2*math.pi/TIME_SAFE(self.rotT))*dt) % (2*math.pi)
            # VPython gira definindo "para cima" e "eixo"; aproximamos o giro em torno do eixo inclinado
            axis = vector(math.sin(self.tilt), 0, math.cos(self.tilt))
            self.body.axis = axis.rotate(angle=self.spin, axis=axis)

        # Update ajudantes destinados ao planeta
        self.lbl.pos = self.body.pos
        self.axis_line.modify(0, pos=self.body.pos - vector(0, math.sin(self.tilt)*self.R, 0))
        self.axis_line.modify(1, pos=self.body.pos + vector(0, math.sin(self.tilt)*self.R, 0))
        if self.rings:
            self.rings.pos = self.body.pos
            self.rings.axis = vector(0, math.cos(self.tilt), 0)

        for m in self.moons:
            m.update(dt)

class Moon:
    def __init__(self, cfg, parent_planet: Planet):
        self.name = cfg["name"]
        MOON_SIZE_MULTIPLIER = 2.5
        self.R = cfg["radius_km"] * RADIUS_SCALE * MOON_SIZE_MULTIPLIER
        self.a = cfg["distance_km"] * DIST_SCALE
        self.T = cfg["orbital_period_days"] * 24 * 3600
        self.rotT = cfg["rotation_period_hours"] * 3600
        self.tilt = math.radians(cfg["tilt_deg"])

        self.parent = parent_planet
        self.theta = 0.0
        self.spin = 0.0

        self.body = sphere(
            pos=self.parent.body.pos + vector(self.a, 0, 0),
            radius=self.R, color=cfg.get("color", color.white),
            shininess=0.8, make_trail=False, emissive=False
        )
        self.lbl = label(pos=self.body.pos, text=self.name, xoffset=0, yoffset=25,
                         height=10, color=color.gray(0.8), box=False, opacity=0,
                         visible=SHOW_LABELS, space=20)

    def update(self, dt):
        if self.T > 0:
            self.theta = (self.theta + (2*math.pi/TIME_SAFE(self.T))*dt) % (2*math.pi)
        self.body.pos = self.parent.body.pos + vector(self.a*math.cos(self.theta), 0, self.a*math.sin(self.theta))
        self.lbl.pos = self.body.pos

# Utilitário para evitar divisão por valores extremamente pequenos
def TIME_SAFE(x):
    return x if abs(x) > 1e-6 else 1e-6

# ---------- Criar Sol ----------
SUN_RADIUS_KM = 696_340
sun = sphere(pos=vector(0,0,0),
             radius=SUN_RADIUS_KM * RADIUS_SCALE,
             color=color.orange,
             emissive=True,  
             shininess=1.0,
             texture=textures.metal) 

# Manter o sol
sun_label = label(pos=sun.pos, text="Sun", xoffset=0, yoffset=60, height=14,
                  color=color.white, box=False, opacity=0, visible=SHOW_LABELS)

# ---------- Instanciar Planetas ----------
planets = []
for cfg in bodies_config:
    p = Planet(cfg, sun)
    planets.append(p)
# Adicionar Lua à Terra
earth = next(p for p in planets if p.name=="Terra")
earth_moon = earth.add_moon(moon_config)

# ---------- Painel de informações ----------
def format_info(p):
    def km(x): return f"{x:,.0f} km".replace(",", ".")
    return (
        f"{p.name}\n"
        f"Raio: {km(p.R / RADIUS_SCALE)}\n"
        f"Distância ao Sol: {km(p.a / DIST_SCALE)}\n"
        f"Período orbital: {p.T/86400:.2f} dias\n"
        f"Rotação: {p.rotT/3600:.2f} h{' (retrógrada)' if p.retrograde else ''}"
    )

info = label(
    pos=vector(scene.width-200, 100, 0), 
    text="Selecione um astro para exibir informações",
    xoffset=0, yoffset=0,
    height=14,
    border=10,
    font='monospace',
    box=True,
    line=True,
    background=color.white,
    pixel_pos=True
)

controls_text = """
CONTROLES INTERATIVOS

MOUSE:
• Arrastar → Orbitar câmera
• Scroll → Zoom
• Clique → Selecionar corpo

TECLADO:
[ESPAÇO] - Pausar/Retomar
[1-8] - Focar planeta
[O] - Órbitas ON/OFF
[L] - Labels ON/OFF  
[T] - Trilhas ON/OFF
[R] - Reset câmera
[I] - Info ON/OFF
[M] - Focar Lua
[ ] ] - Veloc. rotação
"""

controls_menu = label(
    pos=vector(scene.width-200, scene.height-150, 0),
    text=controls_text,
    xoffset=0, yoffset=0,
    height=12,
    border=15,
    font='monospace',
    box=True,
    line=True,
    background=color.white,
    color=color.black,
    pixel_pos=True
)


selected = None

# ---------- Manipuladores de interação ----------
def toggle_orbits():
    global SHOW_ORBITS
    SHOW_ORBITS = not SHOW_ORBITS
    for p in planets:
        p.orbit.visible = SHOW_ORBITS

def toggle_labels():
    global SHOW_LABELS
    SHOW_LABELS = not SHOW_LABELS
    sun_label.visible = SHOW_LABELS
    for p in planets:
        p.lbl.visible = SHOW_LABELS
        for m in p.moons:
            m.lbl.visible = SHOW_LABELS

def toggle_trails():
    global SHOW_TRAILS
    SHOW_TRAILS = not SHOW_TRAILS
    for p in planets:
        p.body.make_trail = SHOW_TRAILS
        if SHOW_TRAILS:
            p.body.clear_trail()
            p.body.retain = 500

def reset_camera():
    global AUTO_ROTATE
    scene.center = vector(0,0,0)
    scene.range = SUN_RADIUS_KM * RADIUS_SCALE * 15
    AUTO_ROTATE = True

def focus_on(p: Planet):
    global AUTO_ROTATE
    scene.center = p.body.pos
    
    target_range = max(p.R * 8, 0.05)
    
    steps = 30   
    for i in range(steps):
        rate(120)  
        scene.range = scene.range + (target_range - scene.range) * 0.2
    
    offset = vector(p.R*5, p.R*3, p.R*5)
    scene.forward = (p.body.pos - offset).norm() 
    AUTO_ROTATE = False

def focus_on_moon(m: Moon):
    global AUTO_ROTATE
    scene.center = m.body.pos
    target_range = max(m.R * 25, 0.05)
    
    relative_dir = norm(m.body.pos - earth.body.pos)
    offset = relative_dir * (m.R * 30)
    
    steps = 30
    for i in range(steps):
        rate(120)
        scene.range += (target_range - scene.range) * 0.2
    
    scene.forward = -relative_dir
    AUTO_ROTATE = False

def auto_rotate_camera(dt):
    if AUTO_ROTATE:
        angle = ROTATION_SPEED * dt
        scene.forward = scene.forward.rotate(angle=angle, axis=vector(0, 1, 0))

def select_body_by_click():
    global selected
    obj = scene.mouse.pick
    if obj is None:
        return
    # Determine se é um planeta, uma lua ou o sol
    if obj is sun:
        selected = None
        info.text = "Sol selecionado"
        reset_camera()
        return
    for p in planets:
        if obj is p.body:
            selected = p
            info.text = format_info(p)
            focus_on(p)
            return
        for m in p.moons:
            if obj is m.body:
                selected = m  
                info.text = f"{m.name} (Lua da Terra)\nRaio: {m.R / RADIUS_SCALE:,.0f} km\nDistância à Terra: {m.a / DIST_SCALE:,.0f} km".replace(",", ".")
                focus_on_moon(m)
                return

def keydown(evt):
    global PAUSED, TIME_SCALE, INFO_VISIBLE
    s = evt.key
    if s == " ":
        PAUSED = not PAUSED
    elif s in ["+", "="]:
        TIME_SCALE *= 1.5
    elif s in ["-", "_"]:
        TIME_SCALE /= 1.5
    elif s.lower() == "o":
        toggle_orbits()
    elif s.lower() == "l":
        toggle_labels()
    elif s.lower() == "t":
        toggle_trails()
    elif s.lower() == "r":
        reset_camera()
    elif s.lower() == "m":
        focus_on_moon(earth_moon)
        info.text = f"Lua da Terra\n" \
                    f"Raio: {earth_moon.R / RADIUS_SCALE:,.0f} km\n" \
                    f"Distância à Terra: {earth_moon.a / DIST_SCALE:,.0f} km".replace(",", ".")

    elif s.lower() == "i":
        INFO_VISIBLE = not INFO_VISIBLE
        info.visible = INFO_VISIBLE
    elif s in ["1","2","3","4","5","6","7","8"]:
        idx = int(s)-1
        if 0 <= idx < len(planets):
            p = planets[idx]
            focus_on(p)
            info.text = format_info(p)

scene.bind("mousedown", lambda evt: select_body_by_click())
scene.bind("keydown", keydown)

reset_camera()

# ---------- Main Loop ----------
prev_time = time.time()
while True:
    rate(120)
    now = time.time()
    real_dt = now - prev_time
    prev_time = now
    dt = 0 if PAUSED else real_dt * TIME_SCALE

    for p in planets:
        p.update(dt)

    sun_label.pos = sun.pos
    auto_rotate_camera(real_dt)
    info.text = info.text 
