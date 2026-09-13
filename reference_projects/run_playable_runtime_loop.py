"""Run from repository root:
PYTHONPATH=src python reference_projects/run_playable_runtime_loop.py
"""
from asteria.validation import PlayableRpgRuntimeLoop

game=PlayableRpgRuntimeLoop()

# Character setup / edits.
game.award_experience(180)
game.unlock_job("alchemist")
game.set_job("secondary","alchemist")
game.allocate_skill("hero_mastery","double_strike_node")
game.equip("main_hand","ember_blade:lab")
game.equip("accessory","echo_charm:lab")
game.attach("ember_blade:lab","rune","venom_rune")
game.add_equipment_growth("ember_blade:lab","weapon_xp",10)

print("FIELD SETUP")
print(game.state())

# Player stands in front of the visible monster and presses Interact.
game.set_player_position(0,0)
game.set_player_facing("right")
game.field_step({"interact":1})

print("\nBATTLE START")
print(game.state())

# Same canonical battle path for player and enemy.
game.player_action("double_strike")
game.enemy_action()

print("\nAFTER ONE EXCHANGE")
print(game.state())

game.finish_encounter()
print("\nRETURNED TO FIELD")
print(game.state())
