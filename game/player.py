import random

class Player:
    def __init__(self, name:str):
        self.name = name
        self.strikes = 0
        self.current_result = None
        


    def add_strike(self, penalty:int):
        self.strikes += penalty

    def roll(self):
        return random.randint(1, 6)

        
    