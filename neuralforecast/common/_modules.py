# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/common.modules.ipynb.

# %% auto 0
__all__ = ['ACTIVATIONS', 'MLP', 'Chomp1d', 'CausalConv1d', 'TemporalConvolutionEncoder', 'TransEncoderLayer', 'TransEncoder',
           'TransDecoderLayer', 'TransDecoder', 'AttentionLayer', 'PositionalEmbedding', 'TokenEmbedding',
           'TimeFeatureEmbedding', 'DataEmbedding', 'Concentrator']

# %% ../../nbs/common.modules.ipynb 3
import math

import torch
import torch.nn as nn
import torch.nn.functional as F

# %% ../../nbs/common.modules.ipynb 5
ACTIVATIONS = ["ReLU", "Softplus", "Tanh", "SELU", "LeakyReLU", "PReLU", "Sigmoid"]

# %% ../../nbs/common.modules.ipynb 7
class MLP(nn.Module):
    """Multi-Layer Perceptron Class

    **Parameters:**<br>
    `in_features`: int, dimension of input.<br>
    `out_features`: int, dimension of output.<br>
    `activation`: str, activation function to use.<br>
    `hidden_size`: int, dimension of hidden layers.<br>
    `num_layers`: int, number of hidden layers.<br>
    `dropout`: float, dropout rate.<br>
    """

    def __init__(
        self, in_features, out_features, activation, hidden_size, num_layers, dropout
    ):
        super().__init__()
        assert activation in ACTIVATIONS, f"{activation} is not in {ACTIVATIONS}"

        self.activation = getattr(nn, activation)()

        # MultiLayer Perceptron
        # Input layer
        layers = [
            nn.Linear(in_features=in_features, out_features=hidden_size),
            self.activation,
            nn.Dropout(dropout),
        ]
        # Hidden layers
        for i in range(num_layers - 2):
            layers += [
                nn.Linear(in_features=hidden_size, out_features=hidden_size),
                self.activation,
                nn.Dropout(dropout),
            ]
        # Output layer
        layers += [nn.Linear(in_features=hidden_size, out_features=out_features)]

        # Store in layers as ModuleList
        self.layers = nn.Sequential(*layers)

    def forward(self, x):
        return self.layers(x)

# %% ../../nbs/common.modules.ipynb 9
class Chomp1d(nn.Module):
    """Chomp1d

    Receives `x` input of dim [N,C,T], and trims it so that only
    'time available' information is used.
    Used by one dimensional causal convolutions `CausalConv1d`.

    **Parameters:**<br>
    `horizon`: int, length of outsample values to skip.
    """

    def __init__(self, horizon):
        super(Chomp1d, self).__init__()
        self.horizon = horizon

    def forward(self, x):
        return x[:, :, : -self.horizon].contiguous()


class CausalConv1d(nn.Module):
    """Causal Convolution 1d

    Receives `x` input of dim [N,C_in,T], and computes a causal convolution
    in the time dimension. Skipping the H steps of the forecast horizon, through
    its dilation.
    Consider a batch of one element, the dilated convolution operation on the
    $t$ time step is defined:

    $\mathrm{Conv1D}(\mathbf{x},\mathbf{w})(t) = (\mathbf{x}_{[*d]} \mathbf{w})(t) = \sum^{K}_{k=1} w_{k} \mathbf{x}_{t-dk}$

    where $d$ is the dilation factor, $K$ is the kernel size, $t-dk$ is the index of
    the considered past observation. The dilation effectively applies a filter with skip
    connections. If $d=1$ one recovers a normal convolution.

    **Parameters:**<br>
    `in_channels`: int, dimension of `x` input's initial channels.<br>
    `out_channels`: int, dimension of `x` outputs's channels.<br>
    `activation`: str, identifying activations from PyTorch activations.
        select from 'ReLU','Softplus','Tanh','SELU', 'LeakyReLU','PReLU','Sigmoid'.<br>
    `padding`: int, number of zero padding used to the left.<br>
    `kernel_size`: int, convolution's kernel size.<br>
    `dilation`: int, dilation skip connections.<br>

    **Returns:**<br>
    `x`: tensor, torch tensor of dim [N,C_out,T] activation(conv1d(inputs, kernel) + bias). <br>
    """

    def __init__(
        self,
        in_channels,
        out_channels,
        kernel_size,
        padding,
        dilation,
        activation,
        stride: int = 1,
    ):
        super(CausalConv1d, self).__init__()
        assert activation in ACTIVATIONS, f"{activation} is not in {ACTIVATIONS}"

        self.conv = nn.Conv1d(
            in_channels=in_channels,
            out_channels=out_channels,
            kernel_size=kernel_size,
            stride=stride,
            padding=padding,
            dilation=dilation,
        )

        self.chomp = Chomp1d(padding)
        self.activation = getattr(nn, activation)()
        self.causalconv = nn.Sequential(self.conv, self.chomp, self.activation)

    def forward(self, x):
        return self.causalconv(x)

# %% ../../nbs/common.modules.ipynb 11
class TemporalConvolutionEncoder(nn.Module):
    """Temporal Convolution Encoder

    Receives `x` input of dim [N,T,C_in], permutes it to  [N,C_in,T]
    applies a deep stack of exponentially dilated causal convolutions.
    The exponentially increasing dilations of the convolutions allow for
    the creation of weighted averages of exponentially large long-term memory.

    **Parameters:**<br>
    `in_channels`: int, dimension of `x` input's initial channels.<br>
    `out_channels`: int, dimension of `x` outputs's channels.<br>
    `kernel_size`: int, size of the convolving kernel.<br>
    `dilations`: int list, controls the temporal spacing between the kernel points.<br>
    `activation`: str, identifying activations from PyTorch activations.
        select from 'ReLU','Softplus','Tanh','SELU', 'LeakyReLU','PReLU','Sigmoid'.<br>

    **Returns:**<br>
    `x`: tensor, torch tensor of dim [N,T,C_out].<br>
    """

    # TODO: Add dilations parameter and change layers declaration to for loop
    def __init__(
        self,
        in_channels,
        out_channels,
        kernel_size,
        dilations,
        activation: str = "ReLU",
    ):
        super(TemporalConvolutionEncoder, self).__init__()
        layers = []
        for dilation in dilations:
            layers.append(
                CausalConv1d(
                    in_channels=in_channels,
                    out_channels=out_channels,
                    kernel_size=kernel_size,
                    padding=(kernel_size - 1) * dilation,
                    activation=activation,
                    dilation=dilation,
                )
            )
            in_channels = out_channels
        self.tcn = nn.Sequential(*layers)

    def forward(self, x):
        # [N,T,C_in] -> [N,C_in,T] -> [N,T,C_out]
        x = x.permute(0, 2, 1).contiguous()
        x = self.tcn(x)
        x = x.permute(0, 2, 1).contiguous()
        return x

# %% ../../nbs/common.modules.ipynb 15
class TransEncoderLayer(nn.Module):
    def __init__(
        self,
        attention,
        hidden_size,
        conv_hidden_size=None,
        dropout=0.1,
        activation="relu",
    ):
        super(TransEncoderLayer, self).__init__()
        conv_hidden_size = conv_hidden_size or 4 * hidden_size
        self.attention = attention
        self.conv1 = nn.Conv1d(
            in_channels=hidden_size, out_channels=conv_hidden_size, kernel_size=1
        )
        self.conv2 = nn.Conv1d(
            in_channels=conv_hidden_size, out_channels=hidden_size, kernel_size=1
        )
        self.norm1 = nn.LayerNorm(hidden_size)
        self.norm2 = nn.LayerNorm(hidden_size)
        self.dropout = nn.Dropout(dropout)
        self.activation = F.relu if activation == "relu" else F.gelu

    def forward(self, x, attn_mask=None):
        new_x, attn = self.attention(x, x, x, attn_mask=attn_mask)

        x = x + self.dropout(new_x)

        y = x = self.norm1(x)
        y = self.dropout(self.activation(self.conv1(y.transpose(-1, 1))))
        y = self.dropout(self.conv2(y).transpose(-1, 1))

        return self.norm2(x + y), attn


class TransEncoder(nn.Module):
    def __init__(self, attn_layers, conv_layers=None, norm_layer=None):
        super(TransEncoder, self).__init__()
        self.attn_layers = nn.ModuleList(attn_layers)
        self.conv_layers = (
            nn.ModuleList(conv_layers) if conv_layers is not None else None
        )
        self.norm = norm_layer

    def forward(self, x, attn_mask=None):
        # x [B, L, D]
        attns = []
        if self.conv_layers is not None:
            for attn_layer, conv_layer in zip(self.attn_layers, self.conv_layers):
                x, attn = attn_layer(x, attn_mask=attn_mask)
                x = conv_layer(x)
                attns.append(attn)
            x, attn = self.attn_layers[-1](x)
            attns.append(attn)
        else:
            for attn_layer in self.attn_layers:
                x, attn = attn_layer(x, attn_mask=attn_mask)
                attns.append(attn)

        if self.norm is not None:
            x = self.norm(x)

        return x, attns

# %% ../../nbs/common.modules.ipynb 16
class TransDecoderLayer(nn.Module):
    def __init__(
        self,
        self_attention,
        cross_attention,
        hidden_size,
        conv_hidden_size=None,
        dropout=0.1,
        activation="relu",
    ):
        super(TransDecoderLayer, self).__init__()
        conv_hidden_size = conv_hidden_size or 4 * hidden_size
        self.self_attention = self_attention
        self.cross_attention = cross_attention
        self.conv1 = nn.Conv1d(
            in_channels=hidden_size, out_channels=conv_hidden_size, kernel_size=1
        )
        self.conv2 = nn.Conv1d(
            in_channels=conv_hidden_size, out_channels=hidden_size, kernel_size=1
        )
        self.norm1 = nn.LayerNorm(hidden_size)
        self.norm2 = nn.LayerNorm(hidden_size)
        self.norm3 = nn.LayerNorm(hidden_size)
        self.dropout = nn.Dropout(dropout)
        self.activation = F.relu if activation == "relu" else F.gelu

    def forward(self, x, cross, x_mask=None, cross_mask=None):
        x = x + self.dropout(self.self_attention(x, x, x, attn_mask=x_mask)[0])
        x = self.norm1(x)

        x = x + self.dropout(
            self.cross_attention(x, cross, cross, attn_mask=cross_mask)[0]
        )

        y = x = self.norm2(x)
        y = self.dropout(self.activation(self.conv1(y.transpose(-1, 1))))
        y = self.dropout(self.conv2(y).transpose(-1, 1))

        return self.norm3(x + y)


class TransDecoder(nn.Module):
    def __init__(self, layers, norm_layer=None, projection=None):
        super(TransDecoder, self).__init__()
        self.layers = nn.ModuleList(layers)
        self.norm = norm_layer
        self.projection = projection

    def forward(self, x, cross, x_mask=None, cross_mask=None):
        for layer in self.layers:
            x = layer(x, cross, x_mask=x_mask, cross_mask=cross_mask)

        if self.norm is not None:
            x = self.norm(x)

        if self.projection is not None:
            x = self.projection(x)
        return x

# %% ../../nbs/common.modules.ipynb 17
class AttentionLayer(nn.Module):
    def __init__(self, attention, hidden_size, n_head, d_keys=None, d_values=None):
        super(AttentionLayer, self).__init__()

        d_keys = d_keys or (hidden_size // n_head)
        d_values = d_values or (hidden_size // n_head)

        self.inner_attention = attention
        self.query_projection = nn.Linear(hidden_size, d_keys * n_head)
        self.key_projection = nn.Linear(hidden_size, d_keys * n_head)
        self.value_projection = nn.Linear(hidden_size, d_values * n_head)
        self.out_projection = nn.Linear(d_values * n_head, hidden_size)
        self.n_head = n_head

    def forward(self, queries, keys, values, attn_mask):
        B, L, _ = queries.shape
        _, S, _ = keys.shape
        H = self.n_head

        queries = self.query_projection(queries).view(B, L, H, -1)
        keys = self.key_projection(keys).view(B, S, H, -1)
        values = self.value_projection(values).view(B, S, H, -1)

        out, attn = self.inner_attention(queries, keys, values, attn_mask)
        out = out.view(B, L, -1)

        return self.out_projection(out), attn

# %% ../../nbs/common.modules.ipynb 18
class PositionalEmbedding(nn.Module):
    def __init__(self, hidden_size, max_len=5000):
        super(PositionalEmbedding, self).__init__()
        # Compute the positional encodings once in log space.
        pe = torch.zeros(max_len, hidden_size).float()
        pe.require_grad = False

        position = torch.arange(0, max_len).float().unsqueeze(1)
        div_term = (
            torch.arange(0, hidden_size, 2).float() * -(math.log(10000.0) / hidden_size)
        ).exp()

        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)

        pe = pe.unsqueeze(0)
        self.register_buffer("pe", pe)

    def forward(self, x):
        return self.pe[:, : x.size(1)]


class TokenEmbedding(nn.Module):
    def __init__(self, c_in, hidden_size):
        super(TokenEmbedding, self).__init__()
        padding = 1 if torch.__version__ >= "1.5.0" else 2
        self.tokenConv = nn.Conv1d(
            in_channels=c_in,
            out_channels=hidden_size,
            kernel_size=3,
            padding=padding,
            padding_mode="circular",
            bias=False,
        )
        for m in self.modules():
            if isinstance(m, nn.Conv1d):
                nn.init.kaiming_normal_(
                    m.weight, mode="fan_in", nonlinearity="leaky_relu"
                )

    def forward(self, x):
        x = self.tokenConv(x.permute(0, 2, 1)).transpose(1, 2)
        return x


class TimeFeatureEmbedding(nn.Module):
    def __init__(self, input_size, hidden_size):
        super(TimeFeatureEmbedding, self).__init__()
        self.embed = nn.Linear(input_size, hidden_size, bias=False)

    def forward(self, x):
        return self.embed(x)


class DataEmbedding(nn.Module):
    def __init__(
        self, c_in, exog_input_size, hidden_size, pos_embedding=True, dropout=0.1
    ):
        super(DataEmbedding, self).__init__()

        self.value_embedding = TokenEmbedding(c_in=c_in, hidden_size=hidden_size)

        if pos_embedding:
            self.position_embedding = PositionalEmbedding(hidden_size=hidden_size)
        else:
            self.position_embedding = None

        if exog_input_size > 0:
            self.temporal_embedding = TimeFeatureEmbedding(
                input_size=exog_input_size, hidden_size=hidden_size
            )
        else:
            self.temporal_embedding = None

        self.dropout = nn.Dropout(p=dropout)

    def forward(self, x, x_mark=None):
        # Convolution
        x = self.value_embedding(x)

        # Add positional (relative withing window) embedding with sines and cosines
        if self.position_embedding is not None:
            x = x + self.position_embedding(x)

        # Add temporal (absolute in time series) embedding with linear layer
        if self.temporal_embedding is not None:
            x = x + self.temporal_embedding(x_mark)

        return self.dropout(x)

# %% ../../nbs/common.modules.ipynb 20
class Concentrator(nn.Module):
    def __init__(
        self,
        n_series: int,
        type: str,
        treatment_var_name: str,
        init_ka1: float,
        init_ka2: float,
        input_size: int,
        h: int,
        freq: int,
        mask_future: bool,
    ):
        super().__init__()

        assert type in [
            "log_normal",
            "sum_total",
            "exponential",
        ], "treatment type not available."

        self.n_series = n_series
        self.type = type
        self.treatment_var_name = treatment_var_name
        self.freq = freq
        self.mask_future = mask_future

        # K parameter for each time-series
        self.k_a1 = nn.Embedding(self.n_series, 1)
        self.k_a2 = nn.Embedding(self.n_series, 1)

        # Initialize k_a
        init_k1 = torch.ones((self.n_series, 1)) * init_ka1
        init_k2 = torch.ones((self.n_series, 1)) * init_ka2
        self.k_a1.weight.data.copy_(init_k1)
        self.k_a2.weight.data.copy_(init_k2)

        self.input_size = input_size
        self.h = h

    def lognormal_treatment_concentration(self, t, k_a, sigma=1):
        t = torch.div(
            t, 60
        )  # 60 minutes --> hours # TODO: make more adaptable to different data freq

        # conc = torch.exp(
        #     torch.negative(torch.pow((torch.log(t + 1e-5) - k_a), 2)) / (2 * sigma**2)
        # ) / (t * sigma * torch.sqrt(torch.tensor(2) * torch.pi) + 1e-5)
        # #Add small increment (1e-5) or else k_a --> [nan]

        conc = torch.exp(
            torch.negative(torch.pow((torch.log(t + 1e-5) - 1), 2)) / (2 * k_a**2)
        ) / (t * k_a * torch.sqrt(torch.tensor(2) * torch.pi) + 1e-5)

        return conc

    def exponential_treatment_concentration(self, t, k_a):
        t = torch.div(t, 60)

        conc = k_a * torch.exp(torch.negative(k_a) * t)

        return conc

    def sum_total(self, treatment_exog, treatment_var, idx):
        b = treatment_var.shape[0]
        l = treatment_var.shape[1]

        # Create [B,L,L] matrix
        ltr = torch.ones(l, l).triu()
        ltr_batch = torch.zeros((b, l, l)).to(treatment_exog.device)
        ltr_batch[:] = ltr

        # Forward fill data
        ltr_fill = torch.mul(ltr_batch, treatment_var.reshape(b, l, 1))
        treatment = ltr_fill.nansum(dim=1)  # [B, L]

        return treatment

    def log_normal(self, treatment_exog, treatment_var, k_a_h, idx):
        b = treatment_var.shape[0]
        l = treatment_var.shape[1]

        idx = idx.long()
        # Constrain k_a with sigmoid
        # k_a = torch.sigmoid(k_a_h(idx))  # [B, 1, 1] for static k_a
        k_a = k_a_h(idx)  # [B, 1, 1] for static k_a

        # Create [B,L,L] matrix
        lt = torch.tensor(range(l))
        ltr = lt.repeat((l, 1)) - lt.reshape(-1, 1)
        ltr[ltr < 0] = 0

        ltr_batch = torch.zeros((b, l, l)).to(treatment_exog.device)
        ltr_batch[:] = ltr

        # Apply frequency
        ltrf_batch = ltr_batch * self.freq

        # Multiple concentration by treatement_var (dose)
        conc = self.lognormal_treatment_concentration(ltrf_batch, k_a)
        scaled_conc = conc * (treatment_var.reshape(b, l, 1))
        treatment = scaled_conc.nansum(dim=1)  # [B, L]

        return treatment

    def exponential(self, treatment_exog, treatment_var, k_a_h, idx):
        b = treatment_var.shape[0]
        l = treatment_var.shape[1]

        idx = idx.long()
        # Constrain k_a with sigmoid
        k_a = torch.sigmoid(k_a_h(idx))  # [B, 1, 1] for static k_a

        # Create [B,L,L] matrix
        lt = torch.tensor(range(l))
        ltr = lt.repeat((l, 1)) - lt.reshape(-1, 1)
        ltr[ltr < 0] = 0

        ltr_batch = torch.zeros((b, l, l)).to(treatment_exog.device)
        ltr_batch[:] = ltr

        # Apply frequency
        ltrf_batch = ltr_batch * self.freq

        # Multiple concentration by treatement_var (dose)
        conc = self.exponential_treatment_concentration(ltrf_batch, k_a)
        scaled_conc = conc * (treatment_var.reshape(b, l, 1))
        treatment = scaled_conc.nansum(dim=1)  # [B, L]

        return treatment

    def forward(self, treatment_exog: torch.Tensor, idx: torch.Tensor) -> torch.Tensor:
        treatment_var1 = treatment_exog[:, :, -2]  # [B,L,C] -> [B,L]
        treatment_var2 = treatment_exog[:, :, -1]  # [B,L,C] -> [B,L]
        # treatment_var3 = treatment_exog[:, :, -3]  # [B,L,C] -> [B,L]

        if self.type == "sum_total":
            treatment1 = self.sum_total(treatment_exog, treatment_var1, idx)
            treatment2 = self.sum_total(treatment_exog, treatment_var2, idx)
            # treatment3 = self.sum_total(treatment_exog, treatment_var3, idx)

        elif self.type == "log_normal":
            treatment1 = self.log_normal(treatment_exog, treatment_var1, self.k_a1, idx)
            treatment2 = self.log_normal(treatment_exog, treatment_var2, self.k_a2, idx)
            # treatment3 = self.log_normal(treatment_exog, treatment_var3, self.k_a3, idx)

        elif self.type == "exponential":
            treatment1 = self.exponential(
                treatment_exog, treatment_var1, self.k_a1, idx
            )
            treatment2 = self.exponential(
                treatment_exog, treatment_var2, self.k_a2, idx
            )
            # treatment3 = self.exponential(treatment_exog, treatment_var3, self.k_a3, idx)

        # Replace treatment variable with concentration
        treatment_exog_out = torch.zeros(treatment_exog.shape).to(treatment_exog.device)
        treatment_exog_out[:, :, :-2] += treatment_exog[:, :, :-2]
        treatment_exog_out[:, :, -2] += treatment1
        treatment_exog_out[:, :, -1] += treatment2

        return treatment_exog_out
