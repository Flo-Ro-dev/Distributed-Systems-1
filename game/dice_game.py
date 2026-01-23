class DiceGame:
    def __init__(self, players, rules):
        self.players = players
        self.rules = rules

        self.current_player_index = 0
       # self.round_start_index = 0
        
        self.last_announcement = None
        self.last_real_roll = None
        self.last_announcer_index = None


    def next_index(self, index):
        return (index + 1) % len(self.players)


    def choose_announcement(self, player, current_roll):

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
        Docstring for choose_doubt
        
        :param self: Description
        :param player: Description
        :param announcement: Description
        """
        raw = input(f"{player.name}: Doubt? {announcement}? j/n: ").strip().lower()
        return raw == "j"
    
    def resolve_reveal(self, doubter_index):
        announcer = self.players[self.last_announcer_index] # Previous player
        doubter = self.players[doubter_index] # Current player

        print("\n --- R E V E A L - - -")
        print(f"{announcer.name} has announced: {self.last_announcement}")
        print(f"His real roll was {self.last_real_roll}")

        if self.last_real_roll == self.last_announcement:
            # Truth --> Penalty for doubter (current player)
            print("Wrong! Penalty for current player")
            doubter.add_strike(1)
     
        else:
            # Lie --> Penalty for previous player
            print("Correct! Penalty for previous player")
            announcer.add_strike(1)
  
        
        # Start new round: Doubter is always starting
        self.current_player_index = doubter_index
       # self.round_start_index = self.current_player_index #

        # Reset round
        self.last_announcement = None
        self.last_real_roll = None
        self.last_announcer_index = None

    def play_turn(self):
        """
        Docstring for play_turn
        
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
        
        # 3.2 Next player does not doubt
        self.current_player_index = doubter_index


    def is_game_over(self):
        """
        When only 1 player is left
        
        :param self: Description
        """
        active = [p for p in self.players if p.strikes < self.rules.max_strikes]
        return len(active) <= 1
    
    def show_status(self):
        print("\n--- Current Scores ---")
        for p in self.players:
            print(f"{p.name}: {p.strikes} strikes")
        print("------------------")

    def run(self):
        print("Start Maexchen!")

        while not self.is_game_over():
            self.show_status()
            self.play_turn()

        self.show_status()
        winner = min(self.players, key=lambda p: p.strikes)
        print(f"\n Winner: {winner.name}")


