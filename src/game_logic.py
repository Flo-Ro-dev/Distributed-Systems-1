# game_logic.py

import random
import hashlib
import os

class MaxleGame:
    def __init__(self, password):
        self.password = password
        
        # Exact hierarchy provided: 31 lowest -> 21 highest (Mäxchen)
        self.order = [
            31, 32,
            41, 42, 43,
            51, 52, 53, 54,
            61, 62, 63, 64, 65,
            11, 22, 33, 44, 55, 66,
            21 # Maexchen
        ]
        # Map value -> rank index (0 to 20)
        self.rank = {value: i for i, value in enumerate(self.order)}

    def normalize(self, d1: int, d2: int):
        """Standardizes dice roll to Mäxle format (HighLow)."""
        high = max(d1, d2)
        low = min(d1, d2)
        val = high * 10 + low
        # Special case: 21 is just 21 (Mäxchen)
        if val == 21: return 21
        return val

    def roll_dice(self):
        """Rolls two dice and returns the normalized Mäxle value."""
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        return self.normalize(d1, d2)

    def is_higher(self, current_val: int, previous_val: int):
        """Returns True if current_val beats previous_val."""
        # If previous was 0 (start of game), anything valid is higher
        if previous_val == 0:
            return True
            
        if current_val not in self.rank or previous_val not in self.rank:
            return False
            
        return self.rank[current_val] > self.rank[previous_val]

    def validate_announcement(self, claim, previous_claim):
        """
        Checks if the user's input is valid:
        1. Must be a real dice combo (in self.order).
        2. Must be strictly higher than previous_claim.
        Returns: (True, "") or (False, "Error Message")
        """
        if claim not in self.rank:
            return False, "That is not a valid dice combination (e.g. 31, 42, 66, 21)."
            
        if not self.is_higher(claim, previous_claim):
            return False, f"You must beat {previous_claim}! ({claim} is too low)"
            
        return True, ""

    def secure_cup(self, real_value, announced_value):
        """Creates the secure token hash."""
        nonce = os.urandom(8).hex()
        raw_string = f"{real_value}{self.password}{nonce}"
        secure_hash = hashlib.sha256(raw_string.encode()).hexdigest()

        return {
            'type': 'TOKEN',
            'turn_count': 0, 
            'announced': announced_value,
            'security': {
                'hash': secure_hash,
                'nonce': nonce,
                'hidden_real': real_value 
            },
            'message': ''
        }

    def verify_hash(self, token):
        sec = token['security']
        real = sec['hidden_real']
        nonce = sec['nonce']
        recalc = hashlib.sha256(f"{real}{self.password}{nonce}".encode()).hexdigest()
        return recalc == sec['hash']