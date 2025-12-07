from ursina import *
import random

app = Ursina()

# --- Configuration ---
FIELD_WIDTH = 100
FIELD_DEPTH = 64

def distance_xz(p1, p2):
    return (Vec3(p1.x, 0, p1.z) - Vec3(p2.x, 0, p2.z)).length()

def sign(x):
    return 1 if x >= 0 else -1

# --- Assets ---
# Simple texture generation (optional, or use colors)

# --- Classes ---
# --- Classes ---
class Player(Entity):
    def __init__(self, position, team, role, control_manager, number):
        super().__init__(
            model='cube',
            color=color.blue if team == 0 else color.red,
            scale=(0.8, 1.8, 0.8),
            position=position,
            collider='box'
        )
        self.team = team # 0 = Blue, 1 = Red
        self.role = role # 'gk', 'def', 'mid', 'att'
        self.base_position = Vec3(position)
        self.control_manager = control_manager
        self.number = number
        
        # Visuals: Number on back/top
        self.number_text = Text(parent=self, text=str(number), color=color.white, scale=4, y=0.6, z=-0.6, billboard=True)

        self.speed = 8
        if role == 'att': self.speed = 9
        if role == 'def': self.speed = 7
        
        # Cursor for active player
        self.cursor = Entity(parent=self, model='quad', texture='circle_outlined', color=color.yellow, scale=(2,2), rotation_x=90, y=-0.9, enabled=False)

    def update(self):
        # Physics / Ground clamp
        self.y = 0.9 
        
        # Logic
        if self.control_manager.active_player == self:
            self.move_user()
            self.cursor.enabled = True
            # visual feedback
            self.color = color.azure if self.team == 0 else color.orange
        else:
            self.ai_logic()
            self.cursor.enabled = False
            self.color = color.blue if self.team == 0 else color.red

    # ... move_user, kick_ball, ai_logic remain mostly same but let's ensure they are preserved ...
    def move_user(self):
        move_speed = self.speed * time.dt
        move_vec = Vec3(0,0,0)
        
        if held_keys['w'] or held_keys['up arrow']: move_vec.z += 1
        if held_keys['s'] or held_keys['down arrow']: move_vec.z -= 1
        if held_keys['a'] or held_keys['left arrow']: move_vec.x -= 1
        if held_keys['d'] or held_keys['right arrow']: move_vec.x += 1
        
        if move_vec.length() > 0:
            self.position += move_vec.normalized() * move_speed
            self.look_at(self.position + move_vec)

        if held_keys['space']:
            self.kick_ball()

    def ai_logic(self):
        dist_to_ball = distance_xz(self.position, ball.position)
        target = self.base_position
        
        aggro_range = 15
        if self.role == 'att': aggro_range = 25
        if self.role == 'mid': aggro_range = 20
        
        if self.role == 'gk':
            target = self.base_position
            if dist_to_ball < 15: # slightly increased GK aggro
                target = ball.position
            target = Vec3(clamp(target.x, -8, 8), target.y, target.z) # Widened GK area

        elif dist_to_ball < aggro_range:
            target = ball.position

        dist_to_target = distance_xz(self.position, target)
        if dist_to_target > 0.5:
            direction = (target - self.position).normalized()
            ai_move_speed = (self.speed * 0.8) * time.dt 
            self.position += direction * ai_move_speed
            self.look_at(target)

    def kick_ball(self):
        dist = distance_xz(self.position, ball.position)
        if dist < 2.5:
            # Kick towards opponent goal
            goal_pos = Vec3(0, 0, FIELD_DEPTH/2) if self.team == 0 else Vec3(0, 0, -FIELD_DEPTH/2)
            
            input_dir = Vec3(0,0,0)
            if held_keys['w']: input_dir.z += 1
            if held_keys['s']: input_dir.z -= 1
            if held_keys['a']: input_dir.x -= 1
            if held_keys['d']: input_dir.x += 1
            
            direction = (goal_pos - self.position).normalized()
            if input_dir.length() > 0:
                direction = (direction + input_dir.normalized()).normalized()

            ball.velocity = direction * 25 + Vec3(0, random.uniform(2, 6), 0)
            Audio('shoot', pitch=random.uniform(0.8, 1.2), loop=False, autoplay=True) 

class Ball(Entity):
    def __init__(self):
        super().__init__(
            model='sphere',
            scale=0.8,
            color=color.white,
            position=(0, 10, 0),
            collider='sphere'
        )
        self.velocity = Vec3(0,0,0)

    def update(self):
        # Physics
        self.position += self.velocity * time.dt
        self.velocity.y -= 25 * time.dt # Gravity
        
        # Ground Collision
        if self.y < 0.4:
            self.y = 0.4
            self.velocity.y *= -0.7 # Bounce
            self.velocity.x *= 0.96 # Friction
            self.velocity.z *= 0.96
            
            if abs(self.velocity.y) < 1:
                self.velocity.y = 0

        # Field Bounds
        if abs(self.x) > FIELD_WIDTH/2: 
            self.x = sign(self.x) * FIELD_WIDTH/2
            self.velocity.x *= -0.8
        if abs(self.z) > FIELD_DEPTH/2:
            # Check Goal
            if abs(self.x) < 7: # Goal width approx
                print("GOAL!") # TODO: Reset
                self.position = (0, 10, 0)
                self.velocity = Vec3(0,0,0)
            else:
                self.z = sign(self.z) * FIELD_DEPTH/2
                self.velocity.z *= -0.8
                
        # Collision with players (Simple push)
        hit_info = self.intersects() 
        if hit_info.hit:
             if isinstance(hit_info.entity, Player):
                 # Dribble / Push
                 push_dir = (self.position - hit_info.entity.position).normalized()
                 self.velocity += push_dir * 5 * time.dt
                 self.position += push_dir * 2 * time.dt

class GameManager(Entity):
    def __init__(self):
        super().__init__()
        self.players = []
        self.active_player = None
        self.team_0_players = []
        self.team_1_players = []

    def setup_teams(self):
        # 4-3-3 Formation (Spread out)
        # Team 0 (Blue) -> Goal at +Z (Attacking), Defending -Z
        # GK, LB, CB, CB, RB, LCM, CAM, RCM, LW, ST, RW
        
        formation_0_coords = [
            (0, -30, 'gk', 1),
            (-22, -22, 'def', 3), (-8, -22, 'def', 4), (8, -22, 'def', 5), (22, -22, 'def', 2), # LB, CB, CB, RB
            (-15, -10, 'mid', 8), (0, -8, 'mid', 10), (15, -10, 'mid', 6), # LCM, CAM, RCM
            (-25, 5, 'att', 11), (0, 10, 'att', 9), (25, 5, 'att', 7) # LW, ST, RW
        ]
        
        # Team 1 (Red) -> Mirror
        formation_1_coords = [
            (0, 30, 'gk', 1),
            (-22, 22, 'def', 3), (-8, 22, 'def', 4), (8, 22, 'def', 5), (22, 22, 'def', 2),
            (-15, 10, 'mid', 8), (0, 8, 'mid', 10), (15, 10, 'mid', 6),
            (-25, -5, 'att', 11), (0, -10, 'att', 9), (25, -5, 'att', 7)
        ]

        for x, z, role, num in formation_0_coords:
            p = Player(position=(x, 1, z), team=0, role=role, control_manager=self, number=num)
            self.players.append(p)
            self.team_0_players.append(p)
            
        for x, z, role, num in formation_1_coords:
            p = Player(position=(x, 1, z), team=1, role=role, control_manager=self, number=num)
            self.players.append(p)
            self.team_1_players.append(p)
            
        self.active_player = self.team_0_players[-2] # ST

    def input(self, key):
        if key == 'tab':
            self.switch_player()
            
    def switch_player(self):
        team = self.team_0_players
        closest_p = min(team, key=lambda p: distance_xz(p.position, ball.position))
        self.active_player = closest_p


# --- Scene Setup ---
ground = Entity(model='plane', scale=(FIELD_WIDTH, 1, FIELD_DEPTH), color=color.rgb(34, 139, 34), collider='box', texture='grass')

# Lines
Entity(parent=ground, model='quad', scale=(0.02, 1), z=0, color=color.white, y=0.01, rotation_x=90) # Center Line
Entity(parent=ground, model='quad', scale=(1, 0.02), x=0.01, color=color.white, y=0.01, rotation_x=90) # Touch line

# Goals
goal_blue = Entity(model='cube', scale=(14, 4, 1), position=(0, 2, -FIELD_DEPTH/2), color=color.white, alpha=0.5)
goal_red = Entity(model='cube', scale=(14, 4, 1), position=(0, 2, FIELD_DEPTH/2), color=color.white, alpha=0.5)

ball = Ball()
game_manager = GameManager()
game_manager.setup_teams()

# Lighting
pivot = Entity()
DirectionalLight(parent=pivot, y=10, z=-10, shadows=True)
AmbientLight(color=color.rgba(100, 100, 100, 100))

# Camera (Elevated)
camera.position = (0, 60, -60)
camera.rotation_x = 55

# UI
msg = Text(text='WASD to Move, SPACE to Kick, TAB to Switch Player', y=0.45, origin=(0,0))

def update():
    # Camera Smooth Follow
    if game_manager.active_player:
        target = game_manager.active_player.position
        
        # Elevated View Offset
        desired_pos = target + Vec3(0, 50, -50)
        camera.position = lerp(camera.position, desired_pos, time.dt * 2)

    if held_keys['escape']:
        application.quit()

if __name__ == '__main__':
    app.run()
