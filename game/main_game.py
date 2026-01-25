from player import Player
from rules import Rules
from dice_game import DiceGame


if __name__ == '__main__':
    
    """
    Main runs the game
    """

    # 1) Rules
    rules = Rules(3, 1, 2)

    # 2) Create players
    players = [
        Player("player_1"),
        Player("player_2"),
        Player("player_3")
    ]

    # 3) Run game
    game = DiceGame(players, rules)
    game.run()