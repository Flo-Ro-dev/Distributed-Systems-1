import random

class MaxleGame:
    """
    Encapsulates the rules and state of the Dice Game (Mäxle).
    """
    def __init__(self):
        self.cup = {
            'turn_count': 0,
            'last_announced': 0,
            'actual_value': 0,
            'message': 'Game Start'
        }

    def generate_fresh_cup(self):
        """Resets the cup for a new round."""
        self.cup = {
            'turn_count': 0,
            'last_announced': 0,
            'actual_value': 0,
            'message': 'New Round Started'
        }
        return self.cup

    def roll_dice(self):
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        # Rule: Higher number is the tens digit (e.g., 4 and 2 becomes 42)
        if d1 < d2:
            d1, d2 = d2, d1
        return int(f"{d1}{d2}")

    def play_turn(self, incoming_token):
        """
        Executes the logic for a single turn: Roll, Compare, Bluff.
        Returns the updated token.
        """
        current_limit = incoming_token['last_announced']
        
        # 1. Roll
        rolled_value = self.roll_dice()
        print(f"\n[GAME] You rolled a: {rolled_value}")

        # 2. Strategy Logic (Auto-Bluff)
        # In a CLI, we might ask the user, but here we automate the 'decision'
        # based on the roll to keep the ring moving.
        announced_value = rolled_value
        
        if announced_value <= current_limit:
            # We must beat the previous value, so we have to lie.
            announced_value = current_limit + 1
            print(f"[GAME] Roll too low ({rolled_value} vs {current_limit}). Bluffing as {announced_value}.")
        else:
            print(f"[GAME] Beat the score! Announcing {announced_value}.")

        # 3. Update Token
        incoming_token['turn_count'] += 1
        incoming_token['last_announced'] = announced_value
        incoming_token['actual_value'] = rolled_value
        incoming_token['message'] = "Turn complete"
        
        return incoming_token