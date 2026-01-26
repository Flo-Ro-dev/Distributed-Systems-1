import random

class Player:
    def __init__(self, name:str):
        self.name = name
        self.strikes = 0
        #self.current_result = None
        
        """
        This class describes the player of the game

        :param name: player name
        :type name: string
        :param strikes: Number of strikes a player has 
        :type max_strikes: int 
        """


    def add_strike(self, penalty:int):
        """
        Add strike if player lost a round
        
        :param penalty: penalty score a player gets
        :type penalty: int
        """

        self.strikes += penalty

    def roll(self):
        """
        Roll the dice
        
        return int between 1 and 6
        """
        return random.randint(1, 6)

        
    