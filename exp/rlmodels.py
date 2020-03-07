import pdb
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
class MLP(nn.Module):
    def __init__(self, nin, nhid, nout, layers=2, to_tensor=None, std=0.1):
        super(MLP, self).__init__()
        self.nin = nin
        self.nhid = nhid
        self.nout = nout
        self.fc_in = nn.Linear(nin, nhid)
        for i in range(1, layers):
            setattr(self, f'fc_h{i}', nn.Linear(nhid, nhid))
        self.fc_out = nn.Linear(nhid, nout)
        self.layers = [self.fc_in] + [getattr(self, f'fc_h{i}') for i in range(1, layers)] + [self.fc_out]
        self.nonlinearity = F.relu
        self.to_tensor = to_tensor
        self.reset_parameters(std)

    def forward(self, x):
        for layer in self.layers[:-1]:
            x = layer(x)
            x = self.nonlinearity(x)
        return self.fc_out(x)

    def reset_parameters(self, std=0.1):
        for p in self.parameters():
            p.data.normal_(std=std)

class LinearPolicy(nn.Module):
    def __init__(self, nin, nout, to_tensor=None, std=0.1):
        super(LinearPolicy, self).__init__()
        self.nin = nin
        self.nout = 1
        self.net = nn.Linear(nin, nout)
        self.to_tensor = to_tensor

    def forward(self, x):
        return self.net(x)

    def reset_parameters(self, std=0.1):
        for p in self.parameters():
            p.data.normal_(std=std)

class DQN(nn.Module):
    def __init__(self, nin, nhid, nout):
        pass

class DVN(nn.Module):
    def __init__(self, nin, nhid, nout):
        pass
