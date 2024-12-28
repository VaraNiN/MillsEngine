import torch
import numpy as np
import re
import time
from typing import List, Any
from colorama import Fore as cf, Style as cs

CORNER_POSITION_MULTI = 1.0
THREE_NEIGH_POSITIONS_MULTI = 1.2
FOUR_NEIGH_POSITIONS_MULTI  = 1.3
LEGAL_MOVES_WEIGHT          = 0.3

#TODO: Implement list of all past board states and the ability to go back to the previous board state
#TODO: Add Openingbook where the program always sets in the four crossings first
#TODO: Optimize away all the triple for loops




### This timer class is based on that of Gertjan van den Burg
### See their article at https://gertjanvandenburg.com/blog/timing_decorator/
class Timer(object):
    def __init__(self):
        self.timers = {}
        self.call_counts = {}
        self._stack = []
        self.start = None

    def add_to_timer(self, name, duration):
        if name not in self.timers:
            self.timers[name] = 0
            self.call_counts[name] = 0
        self.timers[name] += duration
        self.call_counts[name] += 1

    def stack(self, name):
        # stop running timer, start new timer, add name to stack
        if len(self._stack):
            self.add_to_timer(self._stack[0], time.time() - self.start)
        self.start = time.time()
        self._stack.insert(0, name)

    def pop(self):
        # pop name from stack, restart previous timer
        self.add_to_timer(self._stack.pop(0), time.time() - self.start)
        self.start = time.time()

    def print_report(self):
        print("Timing Report:")
        
        # Calculate the maximum length of function names
        max_name_length = max(len(name) for name in self.timers.keys())
        
        # Print the header with dynamic width for function names
        print(f"{'Function':<{max_name_length}} {'Time (s)':<10} {'Calls':<10}")
        print("-" * (max_name_length + 30))
        
        # Print each function's timing report with dynamic width for function names
        for name, duration in self.timers.items():
            print(f"{name:<{max_name_length}} {duration:<10.4f} {self.call_counts[name]:<10}")

TIMER = Timer()

def timer_wrap(func):
    def wrapper(*args, **kwargs):
        name = func.__name__
        TIMER.stack(name)
        ans = func(*args, **kwargs)
        TIMER.pop()
        return ans
    return wrapper


def red(string : str) -> None:
    print(cf.RED + string + cs.RESET_ALL)

@timer_wrap
def check_position(state: torch.tensor) -> bool:
    if state.size() != (3, 3, 3):
        red("Warning: Invalid Board State - Incorrect size")
        print(state)
        return False
    
    if not torch.isin(state, torch.tensor([1, 0, -1])).all():
        red("Warning: Invalid Board State - Contains invalid values")
        print(state)
        return False
    
    if not torch.isin(state[:, 1, 1], torch.tensor([0])).all():
        red("Warning: Invalid Board State - Center positions must be 0")
        print(state)
        return False
    
    if torch.sum(state == 1) > 9:
        red("Warning: Invalid Board State - Too many white stones")
        print(state)
        return False
    
    if abs(torch.sum(state == -1)) > 9:
        red("Warning: Invalid Board State - Too many black stones")
        print(state)
        return False
    
    return True

@timer_wrap
def show_position(state : torch.tensor, check_validity : bool = True, replace_symbols : bool = True) -> None:
    if check_validity:
        if not check_position(state):
            return
        
    board_template = """
        {0}-----------{3}-----------{6}
        |           |           |
        |   {9}-------{12}-------{15}   |
        |   |       |       |   |
        |   |   {18}---{21}---{24}   |   |
        |   |   |       |   |   |
        {1}---{10}---{19}       {25}---{16}---{7}
        |   |   |       |   |   |
        |   |   {20}---{23}---{26}   |   |
        |   |       |       |   |
        |   {11}-------{14}-------{17}   |
        |           |           |
        {2}-----------{5}-----------{8}
        """
    
    input = state.flatten().tolist()
    if replace_symbols:
        input = ["X" if x ==  1 else x for x in input]
        input = ["O" if x == -1 else x for x in input]
        input = [" "  if x ==  0 else x for x in input]
    
    print(board_template.format(*input))

@timer_wrap
def count_stones(state : torch.tensor) -> List[int]:
    white = int(torch.sum(state == 1).item())
    black = int(torch.sum(state == -1).item())
    return [white, black]

@timer_wrap
def input_next_add(state: torch.tensor, colour: int) -> tuple[int]:
    while True:
        move = input("Where should a stone be added? (Format: ring x y): ")
        if re.match(r'^\d \d \d$', move):
            coords = tuple(map(int, move.split()))
            if all(n in {0, 1, 2} for n in coords):
                if not (coords[1] == 1 and coords[2] == 1):
                    if state[coords] == 0:
                        break
                    else:
                        print("Invalid values. There is already a stone there.")
                else:
                    print("Invalid values. x and y cannot both be 1")
            else:
                print("Invalid values. All have to be 0, 1 or 2")
        else:
            print("Invalid format.")

    state[coords] = colour
    return coords

@timer_wrap
def input_next_remove(state: torch.tensor, colour: int) -> None:
    while True:
        move = input("Where should a stone be removed? (Format: ring x y): ")
        if re.match(r'^\d \d \d$', move):
            coords = tuple(map(int, move.split()))
            if all(n in {0, 1, 2} for n in coords):
                if not (coords[1] == 1 and coords[2] == 1):
                    if state[coords] == -colour:
                        break
                    elif state[coords] == colour:
                        print("Invalid values. Cannot remove your own stones.")
                    else:
                        print("Invalid values. No stone there.")
                else:
                    print("Invalid values. x and y cannot both be 1")
            else:
                print("Invalid values. All have to be 0, 1 or 2")
        else:
            print("Invalid format.")

    state[coords] = 0

@timer_wrap
def input_next_move(state: torch.tensor, colour: int, is_late_game : bool = False) -> tuple[int]:
    while True:
        move = input("Please provide the next move in the format (ring_from x_from y_from ring_to x_to y_to): ")
        if re.match(r'^\d \d \d \d \d \d$', move):
            ring_from, x_from, y_from, ring_to, x_to, y_to = map(int, move.split())
            all_coords = tuple(map(int, move.split()))
            coords_from = tuple((ring_from, x_from, y_from))
            coords_to = tuple((ring_to, x_to, y_to ))
            if all(n in {0, 1, 2} for n in all_coords):
                if not (coords_from[1] == 1 and coords_from[2] == 1):
                    if not (coords_to[1] == 1 and coords_to[2] == 1):
                        if state[coords_from] == colour:
                            if state[coords_to] == 0:
                                if is_late_game:
                                    break
                                else:
                                    if coords_to in get_neighbor_free(state)[ring_from][x_from][y_from]:
                                        break
                                    else:
                                        print("Invalid values. Cannot reach target from origin!")
                            else:
                                print("Invalid values. Target is not empty!")
                        else:
                            print("Invalid values. None of your stones is at origin!")
                    else:
                        print("Invalid values. x and y cannot both be 1")
                else:
                    print("Invalid values. x and y cannot both be 1")
            else:
                print("Invalid values. All have to be 0, 1 or 2")
        else:
            print("Invalid format.")

    state[coords_from] = 0
    state[coords_to] = colour
    return coords_to

@timer_wrap
def initialize_neighbour_map() -> List:
    neighbour_indices = [[[[] for _ in range(3)] for _ in range(3)] for _ in range(3)]

    for i in range(3): # Corners
        for j in [0, 2]:
            for k in [0, 2]:
                if j == 0:
                    neighbour_indices[i][j][k].append((i, j+1, k))
                else:
                    neighbour_indices[i][j][k].append((i, j-1, k))

                if k == 0:
                    neighbour_indices[i][j][k].append((i, j, k+1))
                else:
                    neighbour_indices[i][j][k].append((i, j, k-1))

    for i in range(3): # Crossings
        for j, k in [[0, 1], [1, 0], [2, 1], [1, 2]]:
            if j == 1:
                neighbour_indices[i][j][k].append((i, j+1, k))
                neighbour_indices[i][j][k].append((i, j-1, k))

            if k == 1:
                neighbour_indices[i][j][k].append((i, j, k+1))
                neighbour_indices[i][j][k].append((i, j, k-1))

            if i == 0:
                neighbour_indices[i][j][k].append((i+1, j, k))
            if i == 1:
                neighbour_indices[i][j][k].append((i+1, j, k))
                neighbour_indices[i][j][k].append((i-1, j, k))
            if i == 2:
                neighbour_indices[i][j][k].append((i-1, j, k))
            

    return neighbour_indices

neighbors_map = initialize_neighbour_map()

@timer_wrap
def initialize_boardvalues(big_cross : float = FOUR_NEIGH_POSITIONS_MULTI, 
                            little_cross : float = THREE_NEIGH_POSITIONS_MULTI, 
                            corner : float = CORNER_POSITION_MULTI) -> torch.tensor:
    board_value = torch.tensor([
        [[corner, little_cross, corner], 
         [little_cross, 0.0, little_cross], 
         [corner, little_cross, corner]],
        [[corner, big_cross, corner], 
         [big_cross, 0.0, big_cross], 
         [corner, big_cross, corner]],
        [[corner, little_cross, corner], 
         [little_cross, 0.0, little_cross], 
         [corner, little_cross, corner]]
    ])
    return board_value

board_value = initialize_boardvalues(big_cross=FOUR_NEIGH_POSITIONS_MULTI, little_cross=THREE_NEIGH_POSITIONS_MULTI)

@timer_wrap
def get_neighbor_free(state : torch.tensor, neigh_map : List = neighbors_map) -> List:
    """ Returns list of free neighboring cells for each cell"""
    free_neighs = [[[[] for _ in range(3)] for _ in range(3)] for _ in range(3)]
    positions = torch.nonzero(state == 0).tolist()
    for index in positions:
        i, j, k = index
        for neigh in neigh_map[i][j][k]:
            l, m, n = neigh
            free_neighs[l][m][n].append(index)

    return free_neighs

@timer_wrap
def check_mill(state: torch.tensor, move: tuple[int]) -> bool:
    colour = int(state[move])
    if colour not in {1, -1}:
        red("Something went wrong while checking if a mill occurred. state[move] = 0")
        exit()
        
    ring, x, y = move

    if state[ring, x, y - 1] == colour and state[ring, x, y - 2] == colour:
        return True
    if state[ring, x - 1, y] == colour and state[ring, x - 2, y] == colour:
        return True
    if (x == 1 or y == 1) and state[ring - 1, x, y] == colour and state[ring - 2, x, y] == colour:
        return True
    
    return False
    

@timer_wrap
def legal_moves_early(state : torch.tensor) -> List:
    moves = []
    pieces = torch.nonzero(state == 0).tolist()
    for index in pieces:
        if not (index[1] == 1 and index[2] == 1):
            moves.append(tuple(index))
    return moves

@timer_wrap
def legal_moves_mid(state : torch.tensor, colour : int, free_spaces : Any = None) -> List:
    moves = []

    if free_spaces is None:
        free_spaces = get_neighbor_free(state)

    pieces = torch.nonzero(state == colour).tolist()
    for index in pieces:
        i, j, k = index
        if not (j == 1 and k == 1):
            for free in free_spaces[i][j][k]:
                moves.append([(i, j, k), free])
    return moves

@timer_wrap
def legal_moves_end(state : torch.tensor, colour : int, free_spaces : Any = None) -> List:
    moves = []
    pieces = torch.nonzero(state == colour).tolist()
    empty = legal_moves_early(state)
    for index in pieces:
        if not (index[1] == 1 and index[2] == 1):
            for emp in empty:
                moves.append([tuple(index), tuple(emp)])
    return moves

@timer_wrap
def removeable_pieces(state : torch.tensor, colour : int) -> List:
    pieces = torch.nonzero(state == -colour).tolist()
    i = 0
    while i < len(pieces):
        if check_mill(state, tuple(pieces[i])):
            pieces.pop(i)
        else:
            i += 1
    if len(pieces) > 0:
        return pieces
    else:
        return torch.nonzero(state == -colour).tolist()

@timer_wrap
def new_board_state_early(state : torch.tensor, move : tuple[int], colour : int) -> List:
    new_states = []
    original_state = torch.clone(state)
    original_state[move] = colour
    if check_mill(original_state, move):
        for index in removeable_pieces(original_state, colour):
            dummy_state = torch.clone(original_state)
            dummy_state[tuple(index)] = 0
            new_states.append(dummy_state)
    else:
        new_states.append(original_state)
    return new_states

@timer_wrap
def new_board_state_mid(state : torch.tensor, move : List[tuple[int]], colour : int) -> List:
    new_states = []
    original_state = torch.clone(state)
    move_from = move[0]
    move_to = move[1]
    original_state[move_from] = 0
    original_state[move_to] = colour
    if check_mill(original_state, move_to):
        for index in removeable_pieces(original_state, colour):
            dummy_state = torch.clone(original_state)
            dummy_state[tuple(index)] = 0
            new_states.append(dummy_state)
    else:
        new_states.append(original_state)
    return new_states
        
@timer_wrap
def evaluate_position(state : torch.tensor, 
                        board_value : torch.tensor = board_value, 
                        is_early_game : bool = False, 
                        legal_move_weight : float = LEGAL_MOVES_WEIGHT) -> float:

    free_spaces = get_neighbor_free(state)
    terminal = is_terminal_node(state, is_early_game, free_spaces)
    if abs(terminal) == 1:
        return terminal * 9001

    legal_moves_white = len(legal_moves_mid(state, 1, free_spaces))
    legal_moves_black = len(legal_moves_mid(state, -1, free_spaces))

    piece_value = state * board_value
    return float(piece_value.sum()) + legal_move_weight * (legal_moves_white - legal_moves_black)

@timer_wrap
def get_children_early(state : torch.tensor, colour : int):
    children = []
    moves = legal_moves_early(state)
    for i, move in enumerate(moves):
        children += new_board_state_early(state, move, colour)
    return children

@timer_wrap
def is_terminal_node(state : torch.tensor, 
                        is_early_game : bool = False,
                        free_spaces : Any  = None) -> int:

    num_white_stones = torch.sum(state == 1)
    num_black_stones = abs(torch.sum(state == -1))
    if free_spaces is None:
        free_spaces = get_neighbor_free(state)
    legal_moves_white = len(legal_moves_mid(state, 1, free_spaces))
    legal_moves_black = len(legal_moves_mid(state, -1, free_spaces))

    # Check for win
    if not is_early_game:
        if num_white_stones < 3:
            return -1 # Black has won
        if num_black_stones < 3:
            return 1 # White has won

    if num_white_stones > 3:
        if legal_moves_white == 0:
            return -1 # Black has won
    if num_black_stones > 3:
        if legal_moves_black == 0:
            return 1 # White has won
    
    return 0 # Still undecided

@timer_wrap
def minimax_early(node : torch.tensor, 
                depth : int, 
                alpha : float, 
                beta : float, 
                maximizingPlayer : bool) -> tuple[float, torch.tensor]:
    if depth == 0 or abs(is_terminal_node(node, is_early_game = True))==1:
        return evaluate_position(node, is_early_game = True), node

    best_node = None

    if maximizingPlayer:
        maxEval = float('-inf')
        for child in get_children_early(node, 1):
            eval, _ = minimax_early(child, depth - 1, alpha, beta, False)
            if eval > maxEval:
                maxEval = eval
                best_node = child
            alpha = max(alpha, eval)
            if beta <= alpha:
                break  # Beta cut-off
        return maxEval, best_node
    else:
        minEval = float('inf')
        for child in get_children_early(node, -1):
            eval, _ = minimax_early(child, depth - 1, alpha, beta, True)
            if eval < minEval:
                minEval = eval
                best_node = child
            beta = min(beta, eval)
            if beta <= alpha:
                break  # Alpha cut-off
        return minEval, best_node


board_state = torch.zeros((3,3,3), dtype=int)
board_state_history = [[np.nan, board_state]]

PLAYER_COLOUR = 1
MAX_APPROX_EVAL_CALLS = 1e4
BASE_ALPHA = float('-inf')
BASE_BETA = float('inf')


""" board_state[2, 1, 2] = 1
board_state[1, 1, 2] = 1
board_state[1, 2, 1] = 1
board_state[0, 1, 2] = 1
board_state[2, 2, 0] = 1
board_state[2, 2, 2] = 1
board_state[2, 0, 2] = 1

board_state[1, 0, 0] = -1
board_state[1, 0, 1] = -1
board_state[1, 0, 2] = -1
board_state[1, 2, 0] = -1
board_state[0, 0, 1] = -1
board_state[1, 2, 2] = -1 """

if PLAYER_COLOUR == 1:
    player_turn = True
    COMPUTER_MAX = False
else:
    player_turn = False
    COMPUTER_MAX = True


white_placed = 0
black_placed = 0
try:
    while white_placed + black_placed < 18:
        show_position(board_state)
        if player_turn:
            if PLAYER_COLOUR == 1:
                white_placed += 1
                print("Please place white stone %i / 9" %white_placed)
            else:
                black_placed += 1
                print("Please place black stone %i / 9" %black_placed)
            move = input_next_add(board_state, PLAYER_COLOUR)
            if check_mill(board_state, move):
                show_position(board_state)
                input_next_remove(board_state, PLAYER_COLOUR)
            board_state_history.append([np.nan, board_state])
            player_turn = False
        else:
            if PLAYER_COLOUR == 1:
                black_placed += 1
                print("Computer places black stone %i / 9" %black_placed)
            else:
                white_placed += 1
                print("Computer places white stone %i / 9" %white_placed)
            depth = 0
            approx_calls = 1
            while approx_calls < MAX_APPROX_EVAL_CALLS:
                approx_calls *= len(legal_moves_early(board_state)) - depth
                depth += 1
            eval, board_state = minimax_early(board_state, depth, BASE_ALPHA, BASE_BETA, COMPUTER_MAX)
            board_state_history.append([eval, board_state])
            player_turn = True
except KeyboardInterrupt:
    pass

TIMER.print_report()