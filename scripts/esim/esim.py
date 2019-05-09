# coding: utf-8

# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""
Build an Enhancing LSTM model for Natural Language Inference
"""

__all__ = ['ESIM']

from mxnet.gluon import nn, rnn


class ESIM(nn.HybridBlock):
    """"Enhanced LSTM for Natural Language Inference" Qian Chen,
    Xiaodan Zhu, Zhenhua Ling, Si Wei, Hui Jiang, Diana Inkpen. ACL (2017)
    https://arxiv.org/pdf/1609.06038.pdf

    Parameters
    ----------
    nwords: int
        Number of words in vocab
    nword_dims : int
        Dimension of word vector
    nhiddens : int
        Number of hidden units in lstm cell
    ndense_units : int
        Number of hidden units in dense layer
    nclasses : int
        Number of categories
    drop_out : int
        Dropout prob
    """

    def __init__(self, vocab_size, nword_dims, nhidden_units, ndense_units,
                 nclasses, dropout=0.0, **kwargs):
        super(ESIM, self).__init__(**kwargs)
        with self.name_scope():
            self.embedding_encoder = nn.Embedding(vocab_size, nword_dims)
            self.batch_norm = nn.BatchNorm(axis=-1)
            self.lstm_encoder1 = rnn.LSTM(nhidden_units, bidirectional=True)

            self.projection = nn.HybridSequential()
            self.projection.add(nn.BatchNorm(axis=-1),
                                nn.Dropout(dropout),
                                nn.Dense(nhidden_units, activation='relu', flatten=False))

            self.lstm_encoder2 = rnn.LSTM(nhidden_units, bidirectional=True)

            self.fc_encoder = nn.HybridSequential()
            self.fc_encoder.add(nn.BatchNorm(axis=-1),
                                nn.Dropout(dropout),
                                nn.Dense(ndense_units),
                                nn.ELU(),
                                nn.BatchNorm(axis=-1),
                                nn.Dropout(dropout),
                                nn.Dense(nclasses))

            self.avg_pool = nn.GlobalAvgPool1D()
            self.max_pool = nn.GlobalMaxPool1D()

    def _soft_attention_align(self, F, x1, x2, mask1, mask2):
        # x1 shape: (batch, x1_seq_len, nhidden_units*2)
        # x2 shape: (batch, x2_seq_len, nhidden_units*2)
        # mask1 shape: (batch, x1_seq_len)
        # mask2 shape: (batch, x2_seq_len)
        # attention shape: (batch, x1_seq_len, x2_seq_len)
        attention = F.batch_dot(x1, x2, transpose_b=True)

        # weight1 shape: (batch, x1_seq_len, x2_seq_len)
        weight1 = F.softmax(attention + F.expand_dims(mask2, axis=1), axis=-1)
        # x1_align shape: (batch, x1_seq_len, nhidden_units*2)
        x1_align = F.batch_dot(weight1, x2)

        # weight2 shape: (batch, x1_seq_len, x2_seq_len)
        weight2 = F.softmax(attention + F.expand_dims(mask1, axis=2), axis=1)
        # x2_align shape: (batch, x2_seq_len, nhidden_units*2)
        x2_align = F.batch_dot(weight2, x1, transpose_a=True)

        return x1_align, x2_align

    def _submul(self, F, x1, x2):
        mul = F.multiply(x1, x2)
        sub = F.subtract(x1, x2)

        return F.concat(mul, sub, dim=-1)

    def _pooling(self, F, x):
        # x : NCW   C <----> input channels  W <----> seq_len
        # p1, p2 shape: (batch, input channels)
        p1 = F.squeeze(self.avg_pool(x), axis=-1)
        p2 = F.squeeze(self.max_pool(x), axis=-1)

        return F.concat(p1, p2, dim=-1)

    def hybrid_forward(self, F, x1, x2, mask1, mask2):  # pylint: disable=arguments-differ
        # x1, x2 shape: (batch, x1_seq_len), (batch, x2_seq_len)
        # mask1, mask2 shape: (batch, x1_seq_len), (batch, x2_seq_len)
        # x1_embed shape: (batch, x1_seq_len, nword_dims)
        # x2_embed shape: (batch, x2_seq_len, nword_dims)
        x1_embed = self.batch_norm(self.embedding_encoder(x1))
        x2_embed = self.batch_norm(self.embedding_encoder(x2))

        x1_lstm_encode = self.lstm_encoder1(x1_embed)
        x2_lstm_encode = self.lstm_encoder1(x2_embed)

        # attention
        x1_algin, x2_algin = self._soft_attention_align(F, x1_lstm_encode, x2_lstm_encode,
                                                        mask1, mask2)

        # compose
        x1_combined = F.concat(x1_lstm_encode, x1_algin,
                               self._submul(F, x1_lstm_encode, x1_algin), dim=-1)
        x2_combined = F.concat(x2_lstm_encode, x2_algin,
                               self._submul(F, x2_lstm_encode, x2_algin), dim=-1)

        # x1_compose shape: (batch, x1_seq_len, nhidden_units*2)
        # x2_compose shape: (batch, x2_seq_len, nhidden_units*2)
        x1_compose = self.lstm_encoder2(self.projection(x1_combined))
        x2_compose = self.lstm_encoder2(self.projection(x2_combined))

        # aggregate
        # NWC ------> NCW
        x1_compose = F.transpose(x1_compose, axes=(0, 2, 1))
        x2_compose = F.transpose(x2_compose, axes=(0, 2, 1))
        x1_agg = self._pooling(F, x1_compose)
        x2_agg = self._pooling(F, x2_compose)

        # fully connection
        output = self.fc_encoder(F.concat(x1_agg, x2_agg, dim=-1))

        return output
