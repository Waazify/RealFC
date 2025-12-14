from ursina import *
from panda3d.core import CullFaceAttrib
import random

app = Ursina()

# --- Configuration ---
FIELD_WIDTH = 128 # Length (X-axis)
FIELD_DEPTH = 80  # Width (Z-axis)

def distance_xz(p1, p2):
    return (Vec3(p1.x, 0, p1.z) - Vec3(p2.x, 0, p2.z)).length()

def sign(x):
    return 1 if x >= 0 else -1

# --- Assets ---
# Simple texture generation (optional, or use colors)

# --- Classes ---
# --- Classes ---
class Player(Entity):
    def __init__(self, position, team, role, control_manager, number, name):
        super().__init__(
            position=position,
            collider='box',
            scale=(1, 1, 1) # Reset scale for container
        )
        self.team = team # 0 = Real Madrid, 1 = Barcelona
        self.role = role # 'gk', 'def', 'mid', 'att'
        self.base_position = Vec3(position)
        self.control_manager = control_manager
        self.number = number
        self.name = name
        
        # --- Visuals: Branded Uniforms ---
        skin_color = color.rgb(255, 220, 177)
        
        # Default keys
        shirt_color = color.white
        sleeve_color = color.white
        short_color = color.white
        
        if team == 0: # Real Madrid (White)
            shirt_color = color.white
            sleeve_color = color.white
            short_color = color.white
            if role == 'gk':
                shirt_color = color.green
                sleeve_color = color.green
                short_color = color.green

        else: # Barcelona (Blue/Red)
            shirt_color = color.blue
            sleeve_color = color.red # Contrast sleeves
            short_color = color.rgb(0, 0, 100) # Dark Blue
            if role == 'gk':
                shirt_color = color.yellow
                sleeve_color = color.yellow
                short_color = color.black

        # 1. Torso (The "Shirt")
        self.torso = Entity(parent=self, model='cube', color=shirt_color, scale=(0.5, 0.7, 0.3), y=0.1)
        self.create_outline(self.torso)

        # 2. Head
        self.head = Entity(parent=self, model='cube', color=skin_color, scale=(0.3, 0.35, 0.3), y=0.7)
        self.create_outline(self.head)

        # 3. Arms (Sleeves + Skin)
        # Left Arm
        self.l_arm = Entity(parent=self, model='cube', color=sleeve_color, scale=(0.15, 0.6, 0.2), position=(-0.38, 0.1, 0))
        self.create_outline(self.l_arm)
        # Right Arm
        self.r_arm = Entity(parent=self, model='cube', color=sleeve_color, scale=(0.15, 0.6, 0.2), position=(0.38, 0.1, 0))
        self.create_outline(self.r_arm)

        # 4. Legs (Shorts + Skin)
        # Left Leg
        self.l_leg = Entity(parent=self, model='cube', color=short_color, scale=(0.2, 0.7, 0.25), position=(-0.15, -0.65, 0))
        self.create_outline(self.l_leg)
        # Right Leg
        self.r_leg = Entity(parent=self, model='cube', color=short_color, scale=(0.2, 0.7, 0.25), position=(0.15, -0.65, 0))
        self.create_outline(self.r_leg)

        # Number on Back
        self.number_text = Text(parent=self.torso, text=str(number), color=color.white if team==1 else color.black, scale=8, origin=(0,0), z=-0.55)
        self.number_text.rotation_y = 180 # Face backwards 
        
        # Name Tag (Dynamic)
        self.name_tag = Text(parent=self, text=self.name, color=color.white, scale=30, origin=(0,0), y=-1.8, billboard=True, enabled=False)
        self.name_timer = 0

        self.speed = 10 # Slightly higher top speed since acceleration takes time
        if role == 'att': self.speed = 11
        if role == 'def': self.speed = 9
        
        self.velocity = Vec3(0,0,0)
        self.accel = 4.0 # How fast to reach max speed
        self.friction = 5.0 # How fast to stop
        
        # Cursor for active player
        # Ground is at Y=0. Player feet approx Y=0. Cursor needs to be slightly above 0.
        # Player Y=0.9, Feet Y=-0.9 relative to player center? No.
        # Let's set it relative to parent to land on Y=0.02
        self.cursor = Entity(parent=self, model='quad', texture='circle_outlined', color=color.yellow, scale=(2,2), rotation_x=90, y=-0.89, enabled=False)

        # Animation State
        self.anim_state = 'idle' 
        self.anim_timer = 0
        self.run_cycle = 0

    def create_outline(self, part):
        e = Entity(parent=part, model='cube', color=color.black, scale=1.0001, double_sided=False)
        e.shader = None # Basic color

    def update(self):
        # Physics / Ground clamp
        self.y = 0.9 
        
        # Logic
        if self.control_manager.active_player == self:
            self.move_user()
            self.cursor.enabled = True
        else:
            self.ai_logic()
            self.cursor.enabled = False
            
        self.update_animations()
        self.update_name_tag()
        
        # Billboard Name Tag
        # Force name tag to face camera and stay upright
        if self.name_tag.enabled:
            self.name_tag.look_at(camera)
            self.name_tag.rotation_z = 0 # Keep it upright
            self.name_tag.rotation_x = 0 # Optional: maintain verticality or tilt? look_at handles pitch usually.
            # Actually, just look_at(camera) usually works for billboards. 
            # But since parent rotates Y, we might need to compensate or just set world rotation.
            self.name_tag.rotation = camera.rotation

    def update_name_tag(self):
        dist = distance_xz(self.position, ball.position)
        
        # Show name if close to ball
        if dist < 2.0:
            self.name_tag.enabled = True
            self.name_tag.color = color.white # Reset alpha
            self.name_timer = 3.0 # Show for 3 seconds
            
        # Fade out
        if self.name_timer > 0:
            self.name_timer -= time.dt
            if self.name_timer < 1.0:
                 # Fade alpha
                 self.name_tag.color = self.name_tag.color.tint(1) # Hack to set alpha? Ursina Colors are tricky with alpha
                 self.name_tag.alpha = self.name_timer
            
            if self.name_timer <= 0:
                self.name_tag.enabled = False


    def update_animations(self):
        # Override for actions
        if self.anim_state == 'shoot':
            self.anim_timer += time.dt
            # Phase 1: Wind up (0 to 0.1s)
            if self.anim_timer < 0.1:
                self.r_leg.rotation_x = lerp(self.r_leg.rotation_x, -45, time.dt * 20)
                self.l_arm.rotation_x = lerp(self.l_arm.rotation_x, 30, time.dt * 20)
            # Phase 2: Swing (0.1s to 0.3s)
            elif self.anim_timer < 0.3:
                self.r_leg.rotation_x = lerp(self.r_leg.rotation_x, 45, time.dt * 30)
            # Phase 3: Return
            else:
                self.anim_state = 'idle'
                
        # Run / Idle Cycle
        else:
            speed = self.velocity.length()
            if speed > 0.5:
                self.anim_state = 'run'
                self.run_cycle += time.dt * speed * 2 # Faster run = faster cycle
                
                # Sine wave for limbs
                # Legs: Opposite phases
                self.l_leg.rotation_x = math.sin(self.run_cycle) * 30
                self.r_leg.rotation_x = math.sin(self.run_cycle + math.pi) * 30
                
                # Arms: Opposite to legs (Left Leg fwd = Right Arm fwd)
                self.l_arm.rotation_x = math.sin(self.run_cycle + math.pi) * 30
                self.r_arm.rotation_x = math.sin(self.run_cycle) * 30
            else:
                # Idle: Return to 0
                self.anim_state = 'idle'
                self.run_cycle = 0
                self.l_leg.rotation_x = lerp(self.l_leg.rotation_x, 0, time.dt * 10)
                self.r_leg.rotation_x = lerp(self.r_leg.rotation_x, 0, time.dt * 10)
                self.l_arm.rotation_x = lerp(self.l_arm.rotation_x, 0, time.dt * 10)
                self.r_arm.rotation_x = lerp(self.r_arm.rotation_x, 0, time.dt * 10)

    # ... move_user, kick_ball, ai_logic remain mostly same but let's ensure they are preserved ...
    def check_collision(self, proposed_position):
        # Simple sphere/circle collision check
        # We check against all other players
        min_dist = 0.5 # Minimum distance between players
        
        for p in self.control_manager.players:
            if p == self: continue
            
            # Use distance_xz to ignore height differences if any
            if distance_xz(proposed_position, p.position) < min_dist:
                return True
        return False

    def move_user(self):
        input_vec = Vec3(0,0,0)
        
        if held_keys['w'] or held_keys['up arrow']: input_vec.z += 1
        if held_keys['s'] or held_keys['down arrow']: input_vec.z -= 1
        if held_keys['a'] or held_keys['left arrow']: input_vec.x -= 1
        if held_keys['d'] or held_keys['right arrow']: input_vec.x += 1
        
        target_velocity = Vec3(0,0,0)
        
        if input_vec.length() > 0:
            input_vec = input_vec.normalized()
            target_velocity = input_vec * self.speed
            # Look at target but keep Y same as self to avoid tilting
            look_target = self.position + input_vec
            look_target.y = self.y 
            self.look_at(look_target)

        # Apply Acceleration / Friction using lerp
        # If we have input, accelerate to target. If no input, decelerate (friction)
        lerp_speed = self.accel if input_vec.length() > 0 else self.friction
        self.velocity = lerp(self.velocity, target_velocity, time.dt * lerp_speed)

        # Apply Position
        if self.velocity.length() > 0.01:
            proposed_pos = self.position + self.velocity * time.dt
            if not self.check_collision(proposed_pos):
                self.position = proposed_pos
            else:
                self.velocity = Vec3(0,0,0) # Stop on collision

        if held_keys['space']:
            self.kick_ball()

    def ai_logic(self):
        dist_to_ball = distance_xz(self.position, ball.position)
        target = self.base_position
        
        # Check if I am the designated presser for my team
        is_presser = False
        if self.team == 0 and self.control_manager.closest_to_ball_0 == self:
            is_presser = True
        elif self.team == 1 and self.control_manager.closest_to_ball_1 == self:
            is_presser = True

        if self.role == 'gk':
            # Goal position (approximate end of field)
            # Team 0 Goal: -X side (-FIELD_WIDTH/2)
            # Team 1 Goal: +X side (FIELD_WIDTH/2)
            goal_x = -FIELD_WIDTH/2 if self.team == 0 else FIELD_WIDTH/2
            
            # "Save Box" definitions
            # Depth: How far forward from goal line do they engage?
            box_depth_x = 18 
            # Width: Z-axis width
            box_width_z = 20
            
            ball_in_box = False
            # Check Z range (Width)
            if abs(ball.z) < box_width_z / 2: 
                # Check X range (Depth relative to goal)
                if self.team == 0:
                    # Goal at -60. Box extends to -60 + 18 = -42.
                    if ball.x < (goal_x + box_depth_x):
                        ball_in_box = True
                elif self.team == 1:
                    # Goal at +60. Box extends to 60 - 18 = 42.
                    if ball.x > (goal_x - box_depth_x):
                        ball_in_box = True
            
            if ball_in_box:
                # SAVE MODE: Aggressively intercept the ball
                target = ball.position
                # GK Clearing Logic: If close to ball, kick it away!
                if dist_to_ball < 1.5:
                    self.kick_ball(mode='clear')

            else:
                # GUARD MODE: Position between ball and goal
                goal_center = Vec3(goal_x, 0, 0)
                
                # Direction from goal to ball
                dir_to_ball = (ball.position - goal_center).normalized()
                
                # Stand a bit out from the goal line (e.g., 4 units)
                guard_dist = 4
                target = goal_center + dir_to_ball * guard_dist
                
                # Clamp to not go too far wide or forward
                
                # Team 0 (Left Goal) -> Keep X small negative
                if self.team == 0:
                     target.x = clamp(target.x, goal_x, goal_x + 6)
                else:
                     target.x = clamp(target.x, goal_x - 6, goal_x)

                # Clamp Z to goal width
                target.z = clamp(target.z, -6, 6)

        elif is_presser:
            # PRESS: Chase the ball anywhere
            target = ball.position
            
            # POSSESSION: If I have the ball (am very close), decide what to do
            if dist_to_ball < 1.0:
                 self.ai_decide_action()

        else:
            # COVER: Stay near base position but shift towards ball
            # Calculate shift vector (ball position relative to 0,0)
            # We want them to slide slightly towards the ball's side of the field
            
            # Simple approach: LERP between base and ball
            # But clamp it so they don't leave their zone completely
            target = lerp(self.base_position, ball.position, 0.3)
            
            # If ball is VERY far, stick closer to base
            if dist_to_ball > 30:
                target = lerp(self.base_position, ball.position, 0.1)

        dist_to_target = distance_xz(self.position, target)
        
        # AI Physics Movement
        target_velocity = Vec3(0,0,0)
        
        if dist_to_target > 0.5:
            direction = (target - self.position).normalized()
            # Pressers move fast, coverers move slightly slower
            speed_mult = 1.0 if is_presser else 0.8
            if self.role == 'gk': speed_mult = 1.1 # GK is fast
            
            target_speed = self.speed * speed_mult
            target_velocity = direction * target_speed
            
            # Look at target but keep Y same as self to avoid tilting
            look_target = Vec3(target)
            look_target.y = self.y
            self.look_at(look_target)

        # Apply AI Acceleration
        self.velocity = lerp(self.velocity, target_velocity, time.dt * self.accel)
        
        # Apply AI Position
        if self.velocity.length() > 0.01:
            proposed_pos = self.position + self.velocity * time.dt
            if not self.check_collision(proposed_pos):
                self.position = proposed_pos
            else:
                self.velocity = Vec3(0,0,0)

    def ai_decide_action(self):
        # Determine Goal Direction
        enemy_goal_x = FIELD_WIDTH/2 if self.team == 0 else -FIELD_WIDTH/2
        dist_to_goal = abs(self.x - enemy_goal_x)
        
        # 1. SHOOT if close enough 
        if dist_to_goal < 30: 
             # Shoot
             self.kick_ball(mode='shoot')
             return

        # --- Dribble vs Pass Logic ---
        
        # Analyze Surroundings
        enemies = self.control_manager.team_1_players if self.team == 0 else self.control_manager.team_0_players
        forward_dir_sign = 1 if self.team == 0 else -1
        
        blocked_ahead = False
        is_swarmed = False
        nearby_enemies = 0
        
        for e in enemies:
            d = distance_xz(self.position, e.position)
            if d < 5:
                nearby_enemies += 1
                
                # Check if blocking forward path
                # Vector to enemy
                to_enemy = e.position - self.position
                # Project onto forward X axis
                fwd_dot = to_enemy.x * forward_dir_sign
                
                # If enemy is in front (positive dot) and close
                if fwd_dot > 0:
                    blocked_ahead = True

        if nearby_enemies >= 2:
            is_swarmed = True

        # DRIBBLE PRIORITY:
        # If I have space ahead and am not swarmed, keep running!
        if not blocked_ahead and not is_swarmed:
            return # Continue dribbling (default movement)

        # 2. PASS if blocked or swarmed
        pass_target = self.get_best_pass_target()
        
        # If we are desperate (swarmed), lower the bar for a pass
        score_threshold = 0
        if is_swarmed: score_threshold = -10 
        
        if pass_target:
             self.look_at(pass_target.position)
             self.kick_ball(mode='pass', target_entity=pass_target)
             return
             
        # 3. DRIBBLE (Default - handled by movement, but maybe small push?)
        # If we couldn't pass even when blocked, we might just lose the ball or try to force it.
        pass 

    def get_best_pass_target(self):
        best_target = None
        best_score = -999
        
        # Enemy Goal X
        enemy_goal_x = FIELD_WIDTH/2 if self.team == 0 else -FIELD_WIDTH/2
        forward_dir_sign = 1 if self.team == 0 else -1

        teammates = self.control_manager.team_0_players if self.team == 0 else self.control_manager.team_1_players
        
        for mate in teammates:
            if mate == self or mate.role == 'gk': continue
            
            dist = distance_xz(self.position, mate.position)
            
            # Criteria 1: Distance (Open pass: 5 to 30 units)
            if dist < 5 or dist > 40: continue
            
            # Criteria 2: Forward Progress (Is mate closer to enemy goal?)
            # Or simplified: Is mate further 'forward' in X?
            # Team 0 checks if mate.x > self.x
            fw_dist = (mate.x - self.x) * forward_dir_sign
            
            # Score
            score = 0
            score += fw_dist * 2 # Reward forwardness
            score -= abs(dist - 15) * 0.5 # Reward ideal distance (~15)
            
            # Criteria 3: Openness (Distance to nearest enemy)
            # Find nearest enemy to mate
            enemies = self.control_manager.team_1_players if self.team == 0 else self.control_manager.team_0_players
            nearest_enemy_dist = 999
            for e in enemies:
                d = distance_xz(mate.position, e.position)
                if d < nearest_enemy_dist: nearest_enemy_dist = d
            
            if nearest_enemy_dist < 3: score -= 50 # Blocked
            score += nearest_enemy_dist * 1.5 # Reward space
            
            if score > best_score:
                best_score = score
                best_target = mate
                
        return best_target

    def kick_ball(self, mode='shoot', target_entity=None):
        # Cooldown check (handled by checking distance, or maybe a timer? simple is best)
        # If ball is already moving fast away, don't kick
        ball_speed_away = ball.velocity.length()
        if ball_speed_away > 10: 
             # Check if it's moving AWAY
             # If dot product of velocity and dir to ball is positive, it's moving same dir? No.
             return 

        if mode == 'shoot':
             enemy_goal_x = FIELD_WIDTH/2 if self.team == 0 else -FIELD_WIDTH/2
             goal_pos = Vec3(enemy_goal_x, 0, 0)
             direction = (goal_pos - self.position).normalized()
             # Accuracy noise
             direction.z += random.uniform(-0.1, 0.1)
             direction = direction.normalized()
             
             power = 35
             lift = 6
             Audio('shoot', pitch=random.uniform(0.8, 1.2), loop=False, autoplay=True)
             self.anim_state = 'shoot'
             self.anim_timer = 0
             
        elif mode == 'pass':
             if target_entity:
                 direction = (target_entity.position - self.position).normalized()
                 power = 25 # Slower than shot
                 lift = 2
             else:
                 direction = self.forward
                 power = 15
                 lift = 2
             Audio('shoot', pitch=1.5, loop=False, autoplay=True) # Higher pitch for pass
             self.anim_state = 'shoot'
             self.anim_timer = 0

        elif mode == 'clear':
             # Kick towards center / forward
             enemy_goal_x = FIELD_WIDTH/2 if self.team == 0 else -FIELD_WIDTH/2
             goal_pos = Vec3(enemy_goal_x, 0, 0)
             direction = (goal_pos - self.position).normalized()
             direction.z += random.uniform(-0.5, 0.5) # Chaotic clear
             direction = direction.normalized()
             power = 40
             lift = 10
             Audio('shoot', pitch=0.7, loop=False, autoplay=True)
             self.anim_state = 'shoot'
             self.anim_timer = 0

        else: # Standard weak kick / Dribble push handled by collision
             direction = self.forward
             power = 5
             lift = 0

        ball.velocity = direction * power 
        ball.velocity.y = lift

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
        self.outline = Entity(parent=self, model='sphere', color=color.black, scale=1.0001, double_sided=False)
        
    def update(self):
        # Physics
        self.velocity.y -= 25 * time.dt # Gravity
        self.position += self.velocity * time.dt
        
        # Friction
        if self.y <= 0.5:
             self.velocity.x *= 0.98
             self.velocity.z *= 0.98
        
        # Ground Bounce
        if self.y < 0.4:
            self.y = 0.4
            self.velocity.y *= -0.6
            if abs(self.velocity.y) < 1: self.velocity.y = 0

        # Field Bounds (Now X is length, Z is width)
        if self.x > FIELD_WIDTH/2:
            self.x = FIELD_WIDTH/2
            self.velocity.x *= -0.8
        if self.x < -FIELD_WIDTH/2:
            self.x = -FIELD_WIDTH/2
            self.velocity.x *= -0.8
            
        if self.z > FIELD_DEPTH/2:
            self.z = FIELD_DEPTH/2
            self.velocity.z *= -0.8
        if self.z < -FIELD_DEPTH/2:
            self.z = -FIELD_DEPTH/2
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

    def update(self):
        # Determine closest player to ball for each team (Tactical AI)
        if not self.team_0_players or not self.team_1_players: return

        # Team 0
        self.closest_to_ball_0 = min(self.team_0_players, key=lambda p: distance_xz(p.position, ball.position))
        # Team 1
        self.closest_to_ball_1 = min(self.team_1_players, key=lambda p: distance_xz(p.position, ball.position))
        
        # Update UI
        if hasattr(self, 'p1_bar'):
             p1_name = self.active_player.name if self.active_player else self.closest_to_ball_0.name
             self.p1_bar.text = f"Real Madrid: {p1_name} ({self.closest_to_ball_0.role.upper()})"
             
             p2_name = self.closest_to_ball_1.name
             self.p2_bar.text = f"Barcelona: {p2_name} ({self.closest_to_ball_1.role.upper()})"


    def setup_teams(self):
        # Names
        # real_madrid = ["Courtois", "Carvajal", "Militao", "Alaba", "Mendy", "Modric", "Kroos", "Vini Jr", "Rodrygo", "Benzema"]
        barcelona = ["Ter Stegen", "Araujo", "Kounde", "Christensen", "Balde", "Pedri", "Gavi", "De Jong", "Raphinha", "Lewandowski"]
        
        # Team 0: Real Madrid (Left Side)
        # GK
        self.create_player((-60, 0), 0, 'gk', 1, "Casilas")
        # Def x 4
        self.create_player((-45, -20), 0, 'def', 3, "Roberto Carlos") # LB
        self.create_player((-42, -7), 0, 'def', 4, "Ramos")     # CB
        self.create_player((-42, 7), 0, 'def', 5, "Vandijk")    # CB
        self.create_player((-45, 20), 0, 'def', 2, "Dani Alvies")     # RB
        # Mid x 3
        self.create_player((-25, -12), 0, 'mid', 8, "Kroos")      # LCM
        self.create_player((-20, 0), 0, 'mid', 10, "Messi")      # CAM
        self.create_player((-25, 12), 0, 'mid', 5, "Bellingham") # RCM
        # Att x 3
        self.create_player((-10, -20), 0, 'att', 11, "Neymar Jr") # LW
        self.create_player((-5, 0), 0, 'att', 7, "Ronaldo")      # ST
        self.create_player((-10, 20), 0, 'att', 9, "Ali Jr")      # RW

        # Team 1: Barcelona (Right Side)
        # GK
        self.create_player((60, 0), 1, 'gk', 1, barcelona[0])
        # Def x 4
        self.create_player((45, -15), 1, 'def', 2, barcelona[1])
        self.create_player((45, 15), 1, 'def', 3, barcelona[2])
        self.create_player((40, -5), 1, 'def', 4, barcelona[3])
        self.create_player((40, 5), 1, 'def', 5, barcelona[4])
        # Mid x 3
        self.create_player((20, -10), 1, 'mid', 8, barcelona[5])
        self.create_player((20, 10), 1, 'mid', 6, barcelona[6])
        self.create_player((15, 0), 1, 'mid', 21, barcelona[7])
        # Att x 3
        self.create_player((5, -15), 1, 'att', 22, barcelona[8])
        self.create_player((5, 15), 1, 'att', 11, "Dembele") # Extra att
        self.create_player((2, 0), 1, 'att', 9, barcelona[9])

        self.active_player = self.team_0_players[9] # Start with Ronaldo (Index 9: 1gk+4def+3mid+1lw = 9th is ST?)
        # Let's check indices: 0:GK, 1:LB, 2:CB, 3:CB, 4:RB, 5:LCM, 6:CAM, 7:RCM, 8:LW, 9:ST, 10:RW
        
        # Initialize trackers
        self.closest_to_ball_0 = self.active_player
        self.closest_to_ball_1 = self.team_1_players[0]

        # --- UI Player Bars ---
        # Adjusted positions for visibility (origin top-left for left bar, top-right for right bar?)
        # Let's use cleaner alignment.
        self.p1_bar = Text(text="Real Madrid: ", position=(-0.5 * window.aspect_ratio + 0.1, -0.45), origin=(-0.5, 0), scale=1.5, color=color.white)
        self.p2_bar = Text(text="Barcelona: ", position=(0.5 * window.aspect_ratio - 0.6, -0.45), origin=(-0.5, 0), scale=1.5, color=color.white)


    def create_player(self, pos_2d, team, role, number, name):
        # We need to map 2D pos (X,Z) carefully.
        # Arguments are passed as (X, Z) pairs in field logic
        p = Player(position=(pos_2d[0], 1, pos_2d[1]), team=team, role=role, control_manager=self, number=number, name=name)
        self.players.append(p)
        if team == 0: self.team_0_players.append(p)
        else: self.team_1_players.append(p)

    def input(self, key):
        if key == 'tab':
            self.switch_player()
            
    def switch_player(self):
        team = self.team_0_players
        closest_p = min(team, key=lambda p: distance_xz(p.position, ball.position))
        self.active_player = closest_p



# --- Scene Setup ---
# Ground: Bright Green, Horizontal Orientation
ground = Entity(model='plane', scale=(FIELD_WIDTH, 1, FIELD_DEPTH), color=color.rgb(0, 180, 0), collider='box')

# Lines
# Center Line (Thinner, Z-axis)
Entity(parent=ground, model='quad', scale=(0.005, 1), z=0, color=color.white, y=0.01, rotation_x=90) 
# Center Circle
Entity(parent=ground, model='circle', scale=(0.15, 1, 0.25), color=color.white, y=0.01, rotation_x=90, alpha=0.5) 
# Note: Scale on plane parent is (120, 80). 
# Circle scale (0.15, 0.25) -> (120*0.15=18, 80*0.25=20). roughly circle.

# Touch lines (Top/Bottom Z)
Entity(parent=ground, model='quad', scale=(1, 0.01), z=0.49, color=color.white, y=0.01, rotation_x=90) 
Entity(parent=ground, model='quad', scale=(1, 0.01), z=-0.49, color=color.white, y=0.01, rotation_x=90)
# End lines (Left/Right X)
Entity(parent=ground, model='quad', scale=(0.01, 1), x=0.49, color=color.white, y=0.01, rotation_x=90)
Entity(parent=ground, model='quad', scale=(0.01, 1), x=-0.49, color=color.white, y=0.01, rotation_x=90)

# Goals (Oriented on X axis)
# Left Goal (Team 0 Net)
goal_blue = Entity(model='cube', scale=(1, 4, 14), position=(-FIELD_WIDTH/2, 2, 0), color=color.white, alpha=0.5)
# Right Goal (Team 1 Net)
goal_red = Entity(model='cube', scale=(1, 4, 14), position=(FIELD_WIDTH/2, 2, 0), color=color.white, alpha=0.5)

ball = Ball()
game_manager = GameManager()
game_manager.setup_teams()

# Lighting
pivot = Entity()
DirectionalLight(parent=pivot, y=10, z=-10, shadows=True)
AmbientLight(color=color.rgba(100, 100, 100, 100))

# Camera (TV View - Side)
# Positioned at negative Z (Side line), looking at center
camera.position = (0, 50, -75)
camera.rotation_x = 45

# UI
msg = Text(text='WASD to Move, SPACE to Kick, TAB to Switch Player', y=0.45, origin=(0,0))

def update():
    # Camera Smooth Follow
    if game_manager.active_player:
        target = game_manager.active_player.position
        
        # TV Camera: Follow X and Z (Up/Down), Keep relative offset
        # Offset: Y=50 (Height), Z=-60 (Depth relative to player)
        desired_pos = Vec3(target.x, 50, target.z - 60)
        
        camera.position = lerp(camera.position, desired_pos, time.dt * 2)

    if held_keys['escape']:
        application.quit()

if __name__ == '__main__':
    app.run()
