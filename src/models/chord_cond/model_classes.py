import os.path as op
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path
from torch.autograd import Variable

sys.path.append(str(Path(op.abspath(__file__)).parents[2]))
import utils.constants as const

torch.manual_seed(1)

class ChordCondLSTM(nn.Module):
    def __init__(self, vocab_size=None, embed_dim=None, output_dim=None, hidden_dim=None, seq_len=None, 
            batch_size=None, dropout=0.5, batch_norm=True, no_cuda=False, **kwargs):
        super().__init__(**kwargs)
        self.hidden_dim = hidden_dim
        self.num_layers = const.NUM_RNN_LAYERS
        self.batch_norm = batch_norm
        self.no_cuda = no_cuda

        self.chord_fc1 = nn.Linear(const.CHORD_DIM, const.CHORD_EMBED_DIM)
        self.chord_bn = nn.BatchNorm1d(seq_len)
        self.chord_fc2 = nn.Linear(const.CHORD_EMBED_DIM, const.CHORD_EMBED_DIM)

        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.encoder = nn.Linear(embed_dim + const.CHORD_EMBED_DIM, hidden_dim)
        self.encode_bn = nn.BatchNorm1d(seq_len)
        self.lstm = nn.LSTM(hidden_dim, hidden_dim, num_layers=self.num_layers, batch_first=True, dropout=dropout)

        mid_dim = (hidden_dim + output_dim) // 2
        self.decode1 = nn.Linear(hidden_dim, mid_dim)
        self.decode_bn = nn.BatchNorm1d(seq_len)
        self.decode2 = nn.Linear(mid_dim, output_dim)
        self.softmax = nn.LogSoftmax(dim=2)

        self.hidden_and_cell = None
        if batch_size is not None:
            self.init_hidden_and_cell(batch_size)

        if torch.cuda.is_available() and (not self.no_cuda):
            self.cuda()
        return 

    def init_hidden_and_cell(self, batch_size):
        hidden = Variable(torch.zeros(self.num_layers, batch_size, self.hidden_dim))
        cell = Variable(torch.zeros(self.num_layers, batch_size, self.hidden_dim))
        if torch.cuda.is_available() and (not self.no_cuda):
            hidden = hidden.cuda()
            cell = cell.cuda()
        self.hidden_and_cell = (hidden, cell)

    def repackage_hidden_and_cell(self):
        new_hidden = Variable(self.hidden_and_cell[0].data)
        new_cell = Variable(self.hidden_and_cell[1].data)
        if torch.cuda.is_available() and (not self.no_cuda):
            new_hidden = new_hidden.cuda()
            new_cell = new_cell.cuda()
        self.hidden_and_cell = (new_hidden, new_cell)

    def forward(self, data):
        x, chords = data
        chord_embeds = self.chord_fc1(chords)
        if self.batch_norm:
            chord_embeds = self.chord_bn(chord_embeds)
        chord_embeds = self.chord_fc2(F.relu(chord_embeds))

        x_embeds = self.embedding(x)
        encoding = self.encoder(torch.cat([chord_embeds, x_embeds], 2)) # Concatenate along 3rd dimension
        if self.batch_norm:
            encoding = self.encode_bn(encoding)
        encoding = F.relu(encoding)

        lstm_out, self.hidden_and_cell = self.lstm(encoding, self.hidden_and_cell)
        decoding = self.decode1(lstm_out)
        if self.batch_norm:
            decoding = self.decode_bn(decoding)
        decoding = self.decode2(F.relu(decoding))

        output = self.softmax(decoding)
        return output

class PitchLSTM(ChordCondLSTM):
    def __init__(self, **kwargs):
        super().__init__(vocab_size=const.PITCH_DIM, embed_dim=const.PITCH_EMBED_DIM,
                         output_dim=const.PITCH_DIM, **kwargs)

    def data_assembler(self, data_dict):
        data = data_dict[const.PITCH_KEY]
        harmony = data_dict[const.CHORD_KEY]
        if torch.cuda.is_available() and (not self.no_cuda):
            data = data.cuda()
            harmony = harmony.cuda()
        return (data, harmony)

    def target_assembler(self, target_dict):
        target = target_dict[const.PITCH_KEY]
        if torch.cuda.is_available() and (not self.no_cuda):
            target = target.cuda()
        return target

class DurationLSTM(ChordCondLSTM):
    def __init__(self, **kwargs):
        super().__init__(vocab_size=const.DUR_DIM, embed_dim=const.DUR_EMBED_DIM,
                         output_dim=const.DUR_DIM, **kwargs)

    def data_assembler(self, data_dict):
        data = data_dict[const.DUR_KEY]
        harmony = data_dict[const.CHORD_KEY]
        if torch.cuda.is_available() and (not self.no_cuda):
            data = data.cuda()
            harmony = harmony.cuda()
        return (data, harmony)

    def target_assembler(self, target_dict):
        target = target_dict[const.DUR_KEY]
        if torch.cuda.is_available() and (not self.no_cuda):
            target = target.cuda()
        return target