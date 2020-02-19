import pdb
import numpy as np
import pandas as pd
import torch
from utility import S8_GENERATORS, px_mult

def str2tup(s):
    return tuple(int(i) for i in s)

class PermDF:
    '''
    Container class for holding mapping from perm tuple -> distance
    Use it to evaluate policies (mapping from perm tuple -> number).
    '''
    def __init__(self, fname, nbr_func):
        self.df = self.load_df(fname)
        self.dist_dict = self.load_dist_dict()
        self.nbr_func = nbr_func
        self.max_dist = self.df['dist'].max()

    def load_df(self, fname):
        df = pd.read_csv(fname, header=None, dtype={0: str, 1: int})
        df.columns = ['state', 'dist']
        return df

    def load_dist_dict(self):
        return {str2tup(row['state']): row['dist'] for s, row in self.df.iterrows()}

    def __getitem__(self, gtup):
        return self.dist_dict[gtup]

    def __call__(self, gtup):
        return self.dist_dict[gtup]

    def benchmark(self, gtups=None):
        if gtups is None:
            gtups = list(self.dist_dict.keys())

        dist_probs = {}
        probs = []
        for p in gtups:
            dist = self.dist_dict[p]
            true_vals = self.nbr_values(p)
            opt_val = min(true_vals.values())
            opt_nbrs = [n for n, dist in true_vals.items() if dist == opt_val]
            prob_opt_step = len(opt_nbrs) / len(true_vals)
            probs.append(prob_opt_step)

            if dist not in dist_probs:
                dist_probs[dist] = []

            dist_probs[dist].append(prob_opt_step)

        res_prob = {}
        for i in range(1, self.max_dist+1):
            res_prob[i] = np.mean(dist_probs[i])

        return np.mean(probs), res_prob

    def opt_nbr(self, gtup, policy, optmin=True):
        '''
        See if the optimal move given by the policy coicides with the trust
        dist's optimal move
        '''
        true_vals = self.nbr_values(gtup)
        opt_val = min(true_vals.values())
        opt_nbrs = [n for n, dist in true_vals.items() if dist == opt_val]

        pol_vals = self.nbr_values(gtup, policy)

        if optmin:
            opt_pol_nbr = min(pol_vals, key=pol_vals.get)
        else:
            opt_pol_nbr = max(pol_vals, key=pol_vals.get)
        return opt_pol_nbr in opt_nbrs

    def nbr_values(self, gtup, func=None):
        if func is None:
            func = self.__call__

        vals = {}
        gtup_nbrs = self.nbr_func(gtup)

        if hasattr(func, 'forward_tup') and hasattr(func, 'nout') and func.nout > 1:
            res = func.forward_tup([gtup])
            for i, ntup in enumerate(gtup_nbrs):
                vals[ntup] = res[0, i].item()
            return vals

        for ntup in gtup_nbrs:
            if hasattr(func, 'forward_tup'):
                vals[ntup] = func.forward_tup([ntup]).item()
            else:
                vals[ntup] = func(ntup)

        return vals

    # TODO: this is not a proper way doing train test split for perm problem
    def train_test(self, test_ratio):
        perms = list(self.dist_dict.keys())
        np.random.shuffle(perms)
        k = int(test_ratio * len(self.dist_dict))
        test_perms = perms[:k]
        train_perms = perms[k:]
        test_y = np.array([self.dist_dict[p] for p in test_perms])
        train_y = np.array([self.dist_dict[p] for p in train_perms])
        return train_perms, train_y, test_perms, test_y

    def benchmark_policy(self, gtups, policy, optmin=True):
        if len(gtups) == 0:
            return -1

        with torch.no_grad():
            ncorrect = 0
            for g in gtups:
                ncorrect += int(self.opt_nbr(g, policy, optmin))
            return ncorrect / len(gtups)

    def prop_corr_by_dist(self, policy, optmin=True):
        dist_corr = {}
        dist_cnts = {}
        ncorrect = 0
        for ptup, dist in self.dist_dict.items():
            correct = int(self.opt_nbr(ptup, policy, optmin))
            ncorrect += correct
            dist_corr[dist] = dist_corr.get(dist, 0) + correct
            dist_cnts[dist] = dist_cnts.get(dist, 0) + 1

        for i in range(self.max_dist + 1):
            dist_corr[i] = dist_corr[i] / dist_cnts[i]
        prop_corr = ncorrect / len(self.dist_dict)
        return prop_corr, dist_corr

    def opt_move_tup(self, tup):
        dists = [self.dist_dict[t] for t in tup]
        return dists.index(min(dists))

    def random_state(self, dist, cnt):
        subdf = self.df[self.df['dist'] == dist]
        if len(subdf) > cnt:
            subdf = subdf.sample(n=cnt)
        perms = [str2tup(row['state']) for _, row in subdf.iterrows()]
        return perms

    def forward_tup(self, gtup):
        return self.dist_dict[gtup]

def nbrs(p):
    return [px_mult(g, p) for g in S8_GENERATORS]

def test():
    fname = '/home/hopan/github/idastar/s8_dists_red.txt'
    eye = (1, 2, 3, 4, 5, 6, 7, 8)
    pdf = PermDF(fname, nbrs)
    policy = lambda g: g.index(8)
    print(pdf.opt_nbr(eye, policy))

if __name__ == '__main__':
    test()
