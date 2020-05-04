#!/usr/bin/env python
# coding: utf-8
import sys
import os
import time
import json
sys.path.append('/home/hopan/github/SnFFT/exp/')

import argparse
import numpy as np
import pickle
import torch
import torch.nn as nn
import torch.nn.functional as F

import random
from tqdm import tqdm
from logger import get_logger
from cube3 import Cube3, Cube3Edge
from rlmodels import MLPResModel, DVN
from utility import ReplayBuffer, update_params, check_memory
import pdb

from astar import a_star, gen_mlp_model
from cube_main import try_load_weights

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def set_seed(seed):
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)

def can_solve(model, env, state, max_steps, argmin=True):
    if env.is_done(state):
        return True

    for _ in range(max_steps):
        nbrs = env.nbrs(state)
        nbr_vals = model.forward(env.to_tensor(nbrs)).detach()
        if any(env.is_done(n) for n in nbrs):
            return True
        if argmin:
            best_action = nbr_vals.argmin().item()
        else:
            best_action = nbr_vals.argmax().item()
        state = env.step(state, best_action)

    return False

def astar_bench(policy, env, trials, max_exp, scramble_len):
    correct = 0
    solve_lens = []

    done_state = env.start_state()
    hfunc = lambda s: policy.forward(env.to_tensor([s])).item()

    for _ in range(trials):
        start = env.random_state(scramble_len + (1 if random.random() < 0.5 else 0))
        corr, num = a_star(start, done_state, env, hfunc, max_exp)
        if corr:
            solve_lens.append(num)
            correct += 1

    return correct, solve_lens

def benchmark(model, env, trials, max_steps, scramble_len=1000):
    correct = 0

    for _ in range(args.trials):
        state = env.random_state(scramble_len + (1 if random.random() > 0.5 else 0))
        correct += can_solve(model, env, state, max_steps)
    return correct

def unique_logger(sumdir):
    cnt = 0
    logfile = os.path.join(sumdir, f'output.log')
    while os.path.exists(logfile):
        logfile = os.path.join(sumdir, f'output{cnt}.log')
        cnt += 1
    return logfile

def main(args):
    set_seed(args.seed)
    sumdir = os.path.join(f'{args.savedir}', f'{args.env}', f'{args.notes}/seed_{args.seed}')
    if args.savelog:
        try:
            os.makedirs(sumdir)
        except:
            pass
        logfile = unique_logger(sumdir)
        log = get_logger(fname=logfile, stdout=True, tofile=True)
        json.dump(args.__dict__, open(os.path.join(sumdir, 'args.json'), 'w'), indent=2)
        log.info("Saving in: {} | Starting ...".format(logfile))
    else:
        log = get_logger(fname=None, stdout=True, tofile=False)

    if args.env == 'Cube3':
        env = Cube3()
    elif args.env == 'Cube3Edge':
        env = Cube3Edge()
    else:
        log.info(f'{args.env} is not a valid env')
        exit()

    nactions = len(env.moves)
    nin = env.to_tensor([env.start_state()]).numel()
    nout = 1
    updates = 0
    icnt = 0
    start_ep = 0

    replay = ReplayBuffer(nin, args.capacity)
    policy = MLPResModel(nin, args.resfc1, args.resfc2, nout, args.nres, to_tensor=env.to_tensor, std=args.std)
    target = MLPResModel(nin, args.resfc1, args.resfc2, nout, args.nres, to_tensor=env.to_tensor, std=args.std)
    policy.to(device)
    target.to(device)

    if args.init == 'xavier':
        policy.xinit()
        target.xinit()

    if args.loadmodel:
        loaded, start_ep = try_load_weights(sumdir, policy, target)
        if loaded:
            log.info(f'Loaded models! | Starting at epoch: {start_ep}')

    optim = torch.optim.Adam(policy.parameters(), lr=args.lr)
    log.info("Done setup ...")

    for e in range(start_ep, start_ep + args.epochs + 1):
        states = env.random_walk(args.rw_length)
        for state in states:
            action = random.randint(0, len(env.moves) - 1)
            next_state = env.step(state, action)
            reward = 1 if env.is_done(state) else -1
            reward = 0 if env.is_done(state) else 1
            done = 1 if env.is_done(state) else 0
            replay.push(env.to_tensor([state]), action, env.to_tensor([next_state]), reward, done, state, next_state, icnt+1)

            if icnt % args.update_int == 0:
                optim.zero_grad()
                bs, ba, bns, br, bd, bs_tups, bns_tups, bidx = replay.sample(args.batchsize, device)
                bs_nbrs = [n for tup in bs_tups for n in env.nbrs(tup)]
                bs_nbrs_tens = env.to_tensor(bs_nbrs)
                opt_nbr_vals, _ = target.forward(bs_nbrs_tens).detach().reshape(-1, nactions).min(dim=1, keepdim=True)
                loss = F.mse_loss(policy.forward(bs), args.discount * (1 - bd) * opt_nbr_vals + br)
                loss.backward()
                optim.step()

            icnt += 1

        if e % args.target_update == 0 and icnt > 0:
            update_params(target, policy)
            updates += 1

        if e % args.logint == 0:
            #correct = benchmark(policy, env, trials=args.trials, max_steps=args.max_steps, scramble_len=args.scramble_len)
            _astart = time.time()
            correct, solves_lens = astar_bench(policy, env, trials=args.trials, max_exp=args.max_exp, scramble_len=args.scramble_len)
            _atime = (time.time() - _astart) / 60.
            avg = 0
            if correct > 0:
                avg = np.mean(solves_lens)

            log.info(f'Epoch: {e:4d} | A* Solves: {correct/args.trials:.2f} | Avg len: {avg:.2f} | Updates: {updates:4d} | Iters: {icnt:6d} | Mem: {check_memory(verbose=False):.2f}mb | A* time: {_atime:.2f}mins')

            torch.save(policy.state_dict(), os.path.join(sumdir, f'model_last.pt'))

        if e % 10000 == 0 and e > 0:
            torch.save(policy.state_dict(), os.path.join(sumdir, f'model_{e}.pt'))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--env', type=str, default='Cube3')
    parser.add_argument('--savedir', type=str, default='/scratch/hopan/cube/irreps/')
    parser.add_argument('--savelog', action='store_true', default=False)
    parser.add_argument('--loadmodel', action='store_true', default=False)
    parser.add_argument('--notes', type=str, default='test')

    # hyperparams
    parser.add_argument('--lr', type=float, default=0.001)
    parser.add_argument('--capacity', type=int, default=100000)
    parser.add_argument('--batchsize', type=int, default=128)
    parser.add_argument('--discount', type=float, default=1.0)

    # intervals, test params
    parser.add_argument('--epochs', type=int, default=10000)
    parser.add_argument('--logint', type=int, default=200)
    parser.add_argument('--target_update', type=int, default=20)
    parser.add_argument('--update_int', type=int, default=50)
    parser.add_argument('--trials', type=int, default=100)
    parser.add_argument('--max_exp', type=int, default=100)
    parser.add_argument('--rw_length', type=int, default=10)
    parser.add_argument('--max_steps', type=int, default=10)
    parser.add_argument('--scramble_len', type=int, default=20)

    # model params
    parser.add_argument('--std', type=float, default=0.01)
    parser.add_argument('--resfc1', type=int, default='1024')
    parser.add_argument('--resfc2', type=int, default='2048')
    parser.add_argument('--nres', type=int, default='1')
    parser.add_argument('--init', type=str, default='default')

    args = parser.parse_args()
    main(args)
