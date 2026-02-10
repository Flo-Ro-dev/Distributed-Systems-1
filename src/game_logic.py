# game_logic.py

import random
import hashlib
import os

class MaxleGame:
    def __init__(self, password):
        self.password = password
        # Mäxle values, from top (low) to bottom (high), highest value is 21 (Mäxle)
        self.order = [
            31, 32,
            41, 42, 43,
            51, 52, 53, 54,
            61, 62, 63, 64, 65,
            11, 22, 33, 44, 55, 66,
            21
        ]
        self.rank = {value: i for i, value in enumerate(self.order)}

    def normalize(self, d1: int, d2: int):
        """Convert values, to Mäxle values"""
        high = max(d1, d2)
        low = min(d1, d2)
        val = high * 10 + low
        if val == 21: return 21
        return val

    def roll_dice(self):
        """Rolls two dices"""
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        return self.normalize(d1, d2)

    def is_higher(self, current_val: int, previous_val: int):
        """Returns true if current is higher than previouse value, see Mäxle array before"""
        if previous_val == 0:
            return True
            
        if current_val not in self.rank or previous_val not in self.rank:
            return False
            
        return self.rank[current_val] > self.rank[previous_val]

    def validate_announcement(self, claim, previous_claim):
        """
        Checks if dice combo is valis (see Mäxle array)
        Checks if claim is higher than previouse claim
        """
        if claim not in self.rank:
            return False, "That is not a valid dice combination."
            
        if not self.is_higher(claim, previous_claim):
            return False, f"You must beat {previous_claim}! ({claim} is too low)"
            
        return True, ""

    def secure_cup(self, real_value, announced_value):
        """Hash dice roll with password, to not send real value as clear text."""
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