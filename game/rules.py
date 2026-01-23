class Rules:
    def __init__(self,
                 max_strikes: int,
                 penalty:int,
                 penalty_maexchen:int   
                 ):
        """
        :param rank self: Ranking of possible dice results
        """
        self.max_strikes = max_strikes
        self.penalty = penalty
        self.penalty_maexchen = penalty_maexchen
        
        self.order = [
            31, 32,
            41, 42, 43,
            51, 52, 53, 54,
            61, 62, 63, 64, 65,
            11, 22, 33, 44, 55, 66,
            21 # Mäxchen
            ]
        
        self.rank = {value : i for i, value in enumerate(self.order)}

    def normalize(self, d1:int, d2: int):
        """
        Add both dice roles to an integer value that is represented
        in rank.

        :param d1: dice role 1 of player
        :type d1: int
        :param d2: dice role 2 of player
        :type d2: int
        """

        high = max(d1, d2)
        low = min(d1, d2)
        return high*10 + low
    
    def is_higher(self, result_current:int, result_previous:int):
        """
        Compares the dice results between the current and previous 
        player
        
        :param result_current: Dice result of current player
        :type result_current: int
        :param result_previous: Dice result of previous player
        :type result_previous: int
        """

        return self.rank[result_current] > self.rank[result_previous]


    def is_valid_announcement(self, user_input:int):
        """
        Checks if the user announcement is a valid input
        
        :param user_input: User decides what to announce
        return boolean
        """
        return user_input in self.rank



