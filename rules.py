class Rules:
    def __init__(self,
                 max_strikes: int,
                 penalty:int,
                 penalty_maexchen:int   
                 ):
        self.max_strikes = max_strikes
        self.penalty = penalty
        self.penalty_maexchen = penalty_maexchen
        
        self.order = [
            31, 32,
            41, 42, 43,
            51, 52, 53, 54,
            61, 62, 63, 64, 65,
            11, 22, 33, 44, 55, 66,
            21 # Maexchen
            ]
        
        self.rank = {value : i for i, value in enumerate(self.order)}

    def normalize(self, d1:int, d2: int):
        high = max(d1, d2)
        low = min(d1, d2)
        return high*10 + low
    
    def is_higher(self, result_current:int, result_previous:int):
        return self.rank[result_current] > self.rank[result_previous]

    def is_valid_announcement(self, user_input:int):
        return user_input in self.rank

    def to_dict(self):
        return {
            'max_strikes': self.max_strikes,
            'penalty': self.penalty,
            'penalty_maexchen': self.penalty_maexchen
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data['max_strikes'],
            data['penalty'],
            data['penalty_maexchen']
        )
