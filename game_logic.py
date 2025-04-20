# game_logic.py

import random

BOARD_SIZE = 10
SHIP_SIZES = [5, 4, 3, 3, 2]  # Carrier, Battleship, Cruiser, Submarine, Destroyer

class Board:
    def __init__(self):
        self.grid = [['~' for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.ships = []  # List of ship coordinates
        self.hits = set()
        self.misses = set()

    def place_ships_randomly(self):
        for size in SHIP_SIZES:
            placed = False
            while not placed:
                placed = self._place_ship(size)

    def _place_ship(self, size):
        orientation = random.choice(['H', 'V'])
        x = random.randint(0, BOARD_SIZE - 1)
        y = random.randint(0, BOARD_SIZE - 1)
        coords = []

        for i in range(size):
            xi = x + i if orientation == 'H' else x
            yi = y if orientation == 'H' else y + i

            if xi >= BOARD_SIZE or yi >= BOARD_SIZE:
                return False
            if self.grid[yi][xi] != '~':
                return False
            coords.append((xi, yi))

        for xi, yi in coords:
            self.grid[yi][xi] = 'S'
        self.ships.append(set(coords))
        return True

    def fire(self, x, y):
        if (x, y) in self.hits or (x, y) in self.misses:
            return 'already'

        for ship in self.ships:
            if (x, y) in ship:
                self.hits.add((x, y))
                ship.remove((x, y))
                if not ship:
                    self.ships.remove(ship)
                    return 'sunk'
                return 'hit'

        self.misses.add((x, y))
        return 'miss'

    def all_ships_sunk(self):
        return len(self.ships) == 0

    def get_visible_grid(self):
        """Returns a grid view showing hits and misses (for opponents)"""
        view = [['~' for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        for x, y in self.misses:
            view[y][x] = 'O'
        for x, y in self.hits:
            view[y][x] = 'X'
        return view

    def get_full_grid(self):
        """Returns full grid with ships (for own board)"""
        view = [row[:] for row in self.grid]
        for x, y in self.misses:
            view[y][x] = 'O'
        for x, y in self.hits:
            view[y][x] = 'X'
        return view