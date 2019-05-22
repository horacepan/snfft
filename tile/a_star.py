import random
import time
import pdb
import sys
from itertools import permutations
from collections import namedtuple
from queue import PriorityQueue
sys.path.append('../')
import numpy as np
import pandas as pd

from tile_env import TileEnv, neighbors
from heuristic import hamming, manhattan
from heuristic import hamming_grid, manhattan_grid, irrep_gen_func
#from utils import hamming, manhattan
from tile_utils import get_true_df, tup_to_str
State = namedtuple('State', ['moves', 'state'])
IDX_TO_STATE = {idx: p for idx, p in enumerate(permutations(range(1, 10)))}
STATE_TO_IDX = {p: idx for idx, p in IDX_TO_STATE.items()}
TRUE_DISTS = get_true_df()

def grid_to_tup(grid):
    return tuple(i for row in grid for i in row)

def is_done(grid):
    v = 1
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            if v != grid[i, j]:
                return False
            v += 1
    return True

def to_grid(tup):
    n = int(np.sqrt(len(tup)))
    return np.array(tup).reshape(n, n)

def a_star(state, f_heur):
    '''
    state: tuple or grid of puzzle state
    f_heur: function mapping tuple or grid to real number
    '''
    start = time.time()
    to_visit = PriorityQueue()
    curr_state = State(0, STATE_TO_IDX[grid_to_tup(state)])
    to_visit.put((f_heur(state), curr_state))

    done = False
    nodes_explored = 0
    min_heuristic = f_heur(state)
    visited = set()
    sol_moves = -1

    # what things are specific to the 3x3 puzzle?
    while (not to_visit.empty()):
        fitness, (par_moves, par_idx) = to_visit.get()
        par_tup = IDX_TO_STATE[par_idx]
        parent_state = to_grid(par_tup)
        nodes_explored += 1
        visited.add(par_tup)
        if fitness < min_heuristic:
            min_heuristic = fitness

        if is_done(parent_state):
            sol_moves = par_moves
            print('Break early')
            break

        # need to be able to get neighbors from a given state
        # and we want to call the heuristic on the children
        for child in neighbors(parent_state):
            # neighbors returns the grids
            child_prio = par_moves + f_heur(child)
            child_tup = grid_to_tup(child)

            if child_tup in visited:
                continue

            child_idx = STATE_TO_IDX[child_tup]
            child_state = State(par_moves + 1, child_idx)
            to_visit.put((child_prio, child_state))

    end = time.time()
    info = {
        'nodes_explored': nodes_explored,
        'min_heuristic': min_heuristic,
        'sol_moves': sol_moves,
        'elapsed': end - start,
    }
    return info

def get_true_dist(perm):
    try:
        return TRUE_DISTS.loc[perm].distance
    except:
        print('True dist dict: {} | Cant find {} in distance df'.format(len(TRUE_DISTS), perm))
        pdb.set_trace()

def test():
    random.seed(4)
    size = 3
    puzzle = TileEnv(size)

    for _ in range(3):
        puzzle.reset()
        print('Puzzle: {}'.format(puzzle.tup_state()))

        str_state = tup_to_str(puzzle.tup_state())
        print('True dist: {}'.format(get_true_dist(str_state)))

        resh = a_star(puzzle.grid, hamming_grid)
        print(resh)
        resm = a_star(puzzle.grid, manhattan_grid)
        print(resm)

        parts = [(9,), (8, 1)]
        print('Manhattan heuristic using parts: {}'.format(parts))
        irrep_manh = irrep_gen_func(parts, 'manhattan_eval')
        resi = a_star(puzzle.grid, irrep_manh)
        print(resi)

        parts = [(9,), (8, 1)]
        print('Hamming heuristic using parts: {}'.format(parts))
        irrep_hamm = irrep_gen_func(parts, 'hamming_eval')
        resi = a_star(puzzle.grid, irrep_hamm)
        print(resi)

        parts = [(2, 1, 1, 1, 1, 1, 1, 1), (9,), (3, 2, 1, 1, 1, 1), (4, 1, 1, 1, 1, 1), (7, 1, 1)]
        print('Hamming heuristic using parts: {}'.format(parts))
        irrep_hamm = irrep_gen_func(parts, 'hamming_eval')
        resi = a_star(puzzle.grid, irrep_hamm)
        print(resi)

if __name__ == '__main__':
    test()
