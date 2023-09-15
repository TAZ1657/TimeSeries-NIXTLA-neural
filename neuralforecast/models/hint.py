# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/models.hint.ipynb.

# %% auto 0
__all__ = ['get_bottomup_P', 'get_mintrace_ols_P', 'get_mintrace_wls_P', 'get_identity_P', 'HINT']

# %% ../../nbs/models.hint.ipynb 5
from typing import Optional

import numpy as np
import torch

# %% ../../nbs/models.hint.ipynb 7
def get_bottomup_P(S: np.ndarray):
    """BottomUp Reconciliation Matrix.

    Creates BottomUp hierarchical \"projection\" matrix is defined as:
    $$\mathbf{P}_{\\text{BU}} = [\mathbf{0}_{\mathrm{[b],[a]}}\;|\;\mathbf{I}_{\mathrm{[b][b]}}]$$

    **Parameters:**<br>
    `S`: Summing matrix of size (`base`, `bottom`).<br>

    **Returns:**<br>
    `P`: Reconciliation matrix of size (`bottom`, `base`).<br>

    **References:**<br>
    - [Orcutt, G.H., Watts, H.W., & Edwards, J.B.(1968). \"Data aggregation and information loss\". The American
    Economic Review, 58 , 773{787)](http://www.jstor.org/stable/1815532).
    """
    n_series = len(S)
    n_agg = n_series - S.shape[1]
    P = np.zeros_like(S)
    P[n_agg:, :] = S[n_agg:, :]
    P = P.T
    return P


def get_mintrace_ols_P(S: np.ndarray):
    """MinTraceOLS Reconciliation Matrix.

    Creates MinTraceOLS reconciliation matrix as proposed by Wickramasuriya et al.

    $$\mathbf{P}_{\\text{MinTraceOLS}}=\\left(\mathbf{S}^{\intercal}\mathbf{S}\\right)^{-1}\mathbf{S}^{\intercal}$$

    **Parameters:**<br>
    `S`: Summing matrix of size (`base`, `bottom`).<br>

    **Returns:**<br>
    `P`: Reconciliation matrix of size (`bottom`, `base`).<br>

    **References:**<br>
    - [Wickramasuriya, S.L., Turlach, B.A. & Hyndman, R.J. (2020). \"Optimal non-negative
    forecast reconciliation". Stat Comput 30, 1167–1182,
    https://doi.org/10.1007/s11222-020-09930-0](https://robjhyndman.com/publications/nnmint/).
    """
    n_hiers, n_bottom = S.shape
    n_agg = n_hiers - n_bottom

    W = np.eye(n_hiers)

    # We compute reconciliation matrix with
    # Equation 10 from https://robjhyndman.com/papers/MinT.pdf
    A = S[:n_agg, :]
    U = np.hstack((np.eye(n_agg), -A)).T
    J = np.hstack((np.zeros((n_bottom, n_agg)), np.eye(n_bottom)))
    P = J - (J @ W @ U) @ np.linalg.pinv(U.T @ W @ U) @ U.T
    return P


def get_mintrace_wls_P(S: np.ndarray):
    """MinTraceOLS Reconciliation Matrix.

    Creates MinTraceOLS reconciliation matrix as proposed by Wickramasuriya et al.
    Depending on a weighted GLS estimator and an estimator of the covariance matrix of the coherency errors $\mathbf{W}_{h}$.

    $$ \mathbf{W}_{h} = \mathrm{Diag}(\mathbf{S} \mathbb{1}_{[b]})$$

    $$\mathbf{P}_{\\text{MinTraceWLS}}=\\left(\mathbf{S}^{\intercal}\mathbf{W}_{h}\mathbf{S}\\right)^{-1}
    \mathbf{S}^{\intercal}\mathbf{W}^{-1}_{h}$$

    **Parameters:**<br>
    `S`: Summing matrix of size (`base`, `bottom`).<br>

    **Returns:**<br>
    `P`: Reconciliation matrix of size (`bottom`, `base`).<br>

    **References:**<br>
    - [Wickramasuriya, S.L., Turlach, B.A. & Hyndman, R.J. (2020). \"Optimal non-negative
    forecast reconciliation". Stat Comput 30, 1167–1182,
    https://doi.org/10.1007/s11222-020-09930-0](https://robjhyndman.com/publications/nnmint/).
    """
    n_hiers, n_bottom = S.shape
    n_agg = n_hiers - n_bottom

    W = np.diag(S @ np.ones((n_bottom,)))

    # We compute reconciliation matrix with
    # Equation 10 from https://robjhyndman.com/papers/MinT.pdf
    A = S[:n_agg, :]
    U = np.hstack((np.eye(n_agg), -A)).T
    J = np.hstack((np.zeros((n_bottom, n_agg)), np.eye(n_bottom)))
    P = J - (J @ W @ U) @ np.linalg.pinv(U.T @ W @ U) @ U.T
    return P


def get_identity_P(S: np.ndarray):
    # Placeholder function for identity P (no reconciliation).
    pass

# %% ../../nbs/models.hint.ipynb 12
class HINT:
    """HINT

    The Hierarchical Mixture Networks (HINT) are a highly modular framework that
    combines SoTA neural forecast architectures with a task-specialized mixture
    probability and advanced hierarchical reconciliation strategies. This powerful
    combination allows HINT to produce accurate and coherent probabilistic forecasts.

    HINT's incorporates a `TemporalNorm` module into any neural forecast architecture,
    the module normalizes inputs into the network's non-linearities operating range
    and recomposes its output's scales through a global skip connection, improving
    accuracy and training robustness. HINT ensures the forecast coherence via bootstrap
    sample reconciliation that restores the aggregation constraints into its base samples.

    Available reconciliations:<br>
    - BottomUp<br>
    - MinTraceOLS<br>
    - MinTraceWLS<br>
    - Identity

    **Parameters:**<br>
    `h`: int, Forecast horizon. <br>
    `model`: NeuralForecast model, instantiated model class from [architecture collection](https://nixtla.github.io/neuralforecast/models.pytorch.html).<br>
    `S`: np.ndarray, dumming matrix of size (`base`, `bottom`) see HierarchicalForecast's [aggregate method](https://nixtla.github.io/hierarchicalforecast/utils.html#aggregate).<br>
    `reconciliation`: str, HINT's reconciliation method from ['BottomUp', 'MinTraceOLS', 'MinTraceWLS'].<br>
    `alias`: str, optional,  Custom name of the model.<br>
    """

    def __init__(
        self,
        h: int,
        S: np.ndarray,
        model,
        reconciliation: str,
        alias: Optional[str] = None,
    ):
        if model.h != h:
            raise Exception(f"Model h {model.h} does not match HINT h {h}")

        if not model.loss.is_distribution_output:
            raise Exception(
                f"The NeuralForecast model's loss {model.loss} is not a probabilistic objective"
            )

        self.hist_exog_list = model.hist_exog_list
        self.futr_exog_list = model.futr_exog_list
        self.stat_exog_list = model.stat_exog_list

        self.h = h
        self.model = model
        self.early_stop_patience_steps = model.early_stop_patience_steps
        self.S = S
        self.reconciliation = reconciliation
        self.loss = model.loss

        available_reconciliations = dict(
            BottomUp=get_bottomup_P,
            MinTraceOLS=get_mintrace_ols_P,
            MinTraceWLS=get_mintrace_wls_P,
            Identity=get_identity_P,
        )

        if reconciliation not in available_reconciliations:
            raise Exception(f"Reconciliation {reconciliation} not available")

        # Get SP matrix
        self.reconciliation = reconciliation
        if reconciliation == "Identity":
            self.SP = None
        else:
            P = available_reconciliations[reconciliation](S=S)
            self.SP = S @ P

        qs = torch.Tensor((np.arange(self.loss.num_samples) / self.loss.num_samples))
        self.sample_quantiles = torch.nn.Parameter(qs, requires_grad=False)
        self.alias = alias

    def __repr__(self):
        return type(self).__name__ if self.alias is None else self.alias

    def fit(self, dataset, val_size=0, test_size=0, random_seed=None):
        """HINT.fit

        HINT trains on the entire hierarchical dataset, by minimizing a composite log likelihood objective.
        HINT framework integrates `TemporalNorm` into the neural forecast architecture for a scale-decoupled
        optimization that robustifies cross-learning the hierachy's series scales.

        **Parameters:**<br>
        `dataset`: NeuralForecast's `TimeSeriesDataset` see details [here](https://nixtla.github.io/neuralforecast/tsdataset.html)<br>
        `val_size`: int, size of the validation set, (default 0).<br>
        `test_size`: int, size of the test set, (default 0).<br>
        `random_seed`: int, random seed for the prediction.<br>

        **Returns:**<br>
        `self`: A fitted base `NeuralForecast` model.<br>
        """
        self.model.fit(
            dataset=dataset,
            val_size=val_size,
            test_size=test_size,
            random_seed=random_seed,
        )

    def predict(self, dataset, step_size=1, random_seed=None, **data_module_kwargs):
        """HINT.predict

        After fitting a base model on the entire hierarchical dataset.
        HINT restores the hierarchical aggregation constraints using
        bootstrapped sample reconciliation.

        **Parameters:**<br>
        `dataset`: NeuralForecast's `TimeSeriesDataset` see details [here](https://nixtla.github.io/neuralforecast/tsdataset.html)<br>
        `step_size`: int, steps between sequential predictions, (default 1).<br>
        `random_seed`: int, random seed for the prediction.<br>
        `**data_kwarg`: additional parameters for the dataset module.<br>

        **Returns:**<br>
        `y_hat`: numpy predictions of the `NeuralForecast` model.<br>
        """
        # Non-reconciled predictions
        if self.reconciliation == "Identity":
            forecasts = self.model.predict(
                dataset=dataset,
                step_size=step_size,
                random_seed=random_seed,
                **data_module_kwargs,
            )
            return forecasts

        num_samples = self.model.loss.num_samples

        # Hack to get samples by simulating quantiles (samples will be ordered)
        # Mysterious parsing associated to default [mean,quantiles] output
        quantiles_old = self.model.loss.quantiles
        names_old = self.model.loss.output_names
        self.model.loss.quantiles = self.sample_quantiles
        self.model.loss.output_names = ["1"] * (1 + num_samples)
        samples = self.model.predict(
            dataset=dataset,
            step_size=step_size,
            random_seed=random_seed,
            **data_module_kwargs,
        )
        samples = samples[:, 1:]  # Eliminate mean from quantiles
        self.model.loss.quantiles = quantiles_old
        self.model.loss.output_names = names_old

        # Hack requires to break quantiles correlations between samples
        idxs = np.random.choice(num_samples, size=samples.shape, replace=True)
        aux_col_idx = np.arange(len(samples))[:, None] * num_samples
        idxs = idxs + aux_col_idx
        samples = samples.flatten()[idxs]
        samples = samples.reshape(dataset.n_groups, -1, self.h, num_samples)

        # Bootstrap Sample Reconciliation
        # Default output [mean, quantiles]
        samples = np.einsum("ij,jwhp->iwhp", self.SP, samples)
        forecasts = np.quantile(samples, self.model.loss.quantiles, axis=-1)
        forecasts = forecasts.transpose(1, 2, 3, 0)  # [...,samples]
        forecasts = forecasts.reshape(-1, len(self.model.loss.quantiles))

        sample_mean = np.mean(forecasts, axis=-1, keepdims=True)
        forecasts = np.concatenate([sample_mean, forecasts], axis=-1)
        return forecasts

    def set_test_size(self, test_size):
        self.model.test_size = test_size

    def get_test_size(self):
        return self.model.test_size

    def save(self, path):
        """HINT.save

        Save the HINT fitted model to disk.

        **Parameters:**<br>
        `path`: str, path to save the model.<br>
        """
        self.model.trainer.save_checkpoint(path)
