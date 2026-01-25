class DiceGame:
    def __init__(self, players, rules):
        """
        This class describes gameplay
        
        :param players: Players of the game
        :type players: List with player objects
        :param rules: Rules of the game
        :type rules: Object of rules

        :param last_announcement: Score of the previous player
        :type last_announcement: int
        :param last_real_roll: True last roll of the player, to decide whether it was a lie
        :type last_real_roll: int
        :param last_announcer_index: Index of the previous player 
        :type last_announcer_index: int
        """


        self.players = players
        self.rules = rules

        self.current_player_index = 0
       # self.round_start_index = 0
        
        self.last_announcement = None
        self.last_real_roll = None
        self.last_announcer_index = None


    def next_index(self, index):
        """
        Returns next active player (skips eliminated players)
        """
        next_i = (index + 1) % len(self.players)

        while self.players[next_i].strikes >= self.rules.max_strikes:
            next_i = (next_i + 1) % len(self.players)

        return next_i


    def choose_announcement(self, player, current_roll):
        """
        Current player picks his announcement.
        An check if the annoucement is included (step #1 - #4)
        
        :param player: Current player
        :type player: Object of player
        :param current_roll: Roll of the current player
        :type current_roll: int

        :return int of announcement
        """

        while True:

            raw = input("What do you want to announce?").strip()
            # 1) Check input
            if not raw.isdigit() or len(raw) !=2:
                print("Please enter a two digit number")
                continue

            announcement = int(raw)

            # 2) Validation
            if not self.rules.is_valid_announcement(announcement):
                print("Invalid announcement.")
                continue

            # 3) Must be higher than previous announcement
            if self.last_announcement is not None and not self.rules.is_higher(announcement, self.last_announcement):
                print(f"Your announcement must be higher than the previous one: {self.last_announcement}")
                continue
        
            return announcement    
        

    def choose_doubt(self, player, announcement):
        """
        Choose whether a player will doubt the announcement or not (j/n).
        
        :param player: Current player
        :type: Object of player
        :param announcement: announcement of the player
        :type: int
        """

        raw = input(f"{player.name}: Doubt? {announcement}? j/n: ").strip().lower()
        return raw == "j"
    
    def resolve_reveal(self, doubter_index):
        """
        Resolves if a player doubts and resets the round afterwards.
        Gives the doubter/announcer a strike
        
        :param doubter_index: Index of the doubter (current player)
        :type doubter_index:int
        """
        announcer = self.players[self.last_announcer_index] # Previous player
        doubter = self.players[doubter_index] # Current player

        print("\n --- R E V E A L - - -")
        print(f"{announcer.name} has announced: {self.last_announcement}")
        print(f"His real roll was {self.last_real_roll}")

        if self.last_real_roll == self.last_announcement:
            # Truth --> Penalty for doubter (current player)
            if self.last_announcement == self.rules.order[-1]: 
                print(f"Wrong! It was Maexchen. Penalty for current player: + {self.rules.penalty_maexchen} ")
                doubter.add_strike(self.rules.penalty_maexchen)
            else:
                print(f"Wrong! Penalty for current player: + {self.rules.penalty} ")    
     
        else:
            # Lie --> Penalty for previous player
            print("Correct! Penalty for previous player")
            announcer.add_strike(self.rules.penalty)
  
        
        # Start new round: Doubter is always starting
        self.current_player_index = doubter_index
        # self.round_start_index = self.current_player_index #

        # Reset round
        self.last_announcement = None
        self.last_real_roll = None
        self.last_announcer_index = None

    def play_turn(self):
        """
        Plays the turn. Uses methods:
            - roll
            - choose_announcement
            - next_index
            - choose doubt
            - resolve reveal
        
        Starts always with current_player_index = 0
        """

        current_player = self.players[self.current_player_index]

        # 1) Roll the dices
        roll1 = current_player.roll()
        roll2 = current_player.roll()

        real_roll = self.rules.normalize(roll1, roll2)
        print(f"{current_player.name} your current roll is: {real_roll}")

        # 2) Announcement
        announcement = self.choose_announcement(current_player, real_roll)

        print(f"{current_player.name} calls: {announcement}")

        # Save state
        self.last_real_roll = real_roll
        self.last_announcement = announcement
        self.last_announcer_index = self.current_player_index

        # 3) Resolving
        # 3.1) Next player doubts
        doubter_index = self.next_index(self.current_player_index)
        doubter = self.players[doubter_index]
        
        if self.choose_doubt(doubter, announcement):
            self.resolve_reveal(doubter_index)
            return # turn ends here
        
        # 3.2) Next player does not doubt
        # Special Rule: Maexchen is not doubted (belived) -> +1 Strike, Start new round
        if announcement == self.rules.order[-1]:
            print(f"{doubter.name} believes Maexchen. +{self.rules.penalty} strike. New round.")
            doubter.add_strike(self.rules.penalty)

            # doubter starts new round
            self.current_player_index = doubter_index

            # reset round
            self.last_announcement = None
            self.last_real_roll = None
            self.last_announcer_index = None
            return  # Turn endet hier

        # normal weiter spielen
        self.current_player_index = doubter_index


    def is_game_over(self):
        """
        When only 1 player has no strikes
        
        :returns active players left
        """
        active = [p for p in self.players if p.strikes < self.rules.max_strikes]
        return len(active) <= 1
    
    def show_status(self):
        """
        Shows the current game status (strokes) of the players

        """
        print("\n--- Current Scores ---")
        for p in self.players:
            print(f"{p.name}: {p.strikes} strikes")
        print("------------------")

    def run(self):
        """
        Runs the game.
        """
        print("Start Maexchen!")

        while not self.is_game_over():
            self.show_status()
            self.play_turn()

        self.show_status()
        winner = min(self.players, key=lambda p: p.strikes)
        print(f"\n Winner: {winner.name}")


