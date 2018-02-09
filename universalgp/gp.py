# -*- coding: utf-8 -*-
"""
Created on Sun Jan 28 18:56:08 2018

@author: zc223
"""

import numpy as np
import tensorflow as tf

from . import inf
from . import util


class GaussianProcess:
    """
    The class is the main Gaussian Process model.

    Parameters
    ----------
    cov_func : prior covariance function (kernel).
    # mean_func : prior mean function.
    lik_func : likelihood function p(y|f).
    inf_func : function specifying the inference method.
    inducing_inputs : ndarray
        An array of initial inducing input locations. Dimensions: num_inducing * input_dim.
        Default: inducing_input = train inputs (for exact inference)
    """
    def __init__(self,
                 inducing_inputs,
                 cov_func,
                 inf_func,
                 # mean_func=mean.ZeroOffset(),
                 lik_func):

        self.cov = cov_func
        # self.mean = mean_func
        self.inf = inf_func
        self.lik = lik_func

        self.input_dim = inducing_inputs.shape[-1]
        self.raw_likelihood_params = self.lik.get_params()
        self.raw_kernel_params = sum([k.get_params() for k in self.cov], [])

        # Define placeholder variables for training and predicting.
        self.num_train = tf.placeholder(tf.float32, shape=[], name="num_train")
        self.train_inputs = tf.placeholder(tf.float32, shape=[None, self.input_dim],
                                           name="train_inputs")
        self.train_outputs = tf.placeholder(tf.float32, shape=[None, None],
                                            name="train_outputs")
        self.test_inputs = tf.placeholder(tf.float32, shape=[None, self.input_dim],
                                          name="test_inputs")

        # Define all parameters that get optimized directly in raw form. Some parameters get
        # transformed internally to maintain certain pre-conditions.

        if isinstance(self.inf, inf.Variational):
            self.obj_func, self.predictions, self.var_param = self.inf.variation_inference(self.train_inputs,
                                                                                           self.train_outputs,
                                                                                           self.num_train,
                                                                                           self.test_inputs,
                                                                                           inducing_inputs)
        if isinstance(self.inf, inf.Exact):
            self.obj_func, self.predictions, self.var_param = self.inf.exact_inference(self.train_inputs,
                                                                                       self.train_outputs,
                                                                                       self.num_train,
                                                                                       self.test_inputs)

        # config = tf.ConfigProto(log_device_placement=True, allow_soft_placement=True)
        # Do all the tensorflow bookkeeping.
        self.session = tf.Session()
        self.optimizer = None
        self.train_step = None

    def fit(self, data, optimizer, var_steps=10, epochs=200, batch_size=None,
            display_step=1):
        """
        Fit the Gaussian process model to the given data.

        Parameters
        ----------
        data : subclass of datasets.DataSet
            The train inputs and outputs.
        optimizer : TensorFlow optimizer
            The optimizer to use in the fitting process.
        var_steps : int
            Number of steps to update    variational parameters using variational objective (elbo).
        epochs : int
            The number of epochs to optimize the model for.
        batch_size : int
            The number of datapoints to use per mini-batch when training. If batch_size is None,
            then we perform batch gradient descent.
        display_step : int
            The frequency at which the objective values are printed out.
        """

        num_train = data.num_examples

        if batch_size is None:
            batch_size = num_train

        hyper_param = self.raw_kernel_params + self.raw_likelihood_params  # hyperparameters

        if self.optimizer != optimizer:
            self.optimizer = optimizer

            self.train_step = optimizer.minimize(sum(self.obj_func.values()), var_list=self.var_param + hyper_param)

            self.session.run(tf.global_variables_initializer())

        iter_num = 0
        while data.epochs_completed < epochs:
            var_iter = 0
            while var_iter < var_steps:
                batch = data.next_batch(batch_size)
                self.session.run(self.train_step, feed_dict={self.train_inputs: batch[0],
                                                             self.train_outputs: batch[1],
                                                             self.num_train: num_train})
                if var_iter % display_step == 0:
                    self._print_state(data, num_train, iter_num)
                var_iter += 1
                iter_num += 1

    def predict(self, data, test_inputs, batch_size=None):
        """
        Predict outputs given inputs.

        Parameters
        ----------
        data : subclass of datasets.DataSet
            The train inputs and outputs.
        test_inputs : ndarray
            Points on which we wish to make predictions. Dimensions: num_test * input_dim.
        batch_size : int
            The size of the batches we make predictions on. If batch_size is None, predict on the
            entire test set at once.

        Returns
        -------
        ndarray
            The predicted mean of the test inputs. Dimensions: num_test * output_dim.
        ndarray
            The predicted variance of the test inputs. Dimensions: num_test * output_dim.
        """
        if batch_size is None:
            num_batches = 1
        else:
            num_batches = util.ceil_divide(test_inputs.shape[0], batch_size)

        test_inputs = np.array_split(test_inputs, num_batches)
        pred_means = [0.0] * num_batches
        pred_vars = [0.0] * num_batches

        for i in range(num_batches):
            pred_means[i], pred_vars[i] = self.session.run(
                self.predictions, feed_dict={self.test_inputs: test_inputs[i],
                                             self.train_inputs: data.X,
                                             self.train_outputs: data.Y,
                                             self.num_train: data.num_examples})

        return np.concatenate(pred_means, axis=0), np.concatenate(pred_vars, axis=0)

    def _print_state(self, data, num_train, iter_num):
        """Print the current state."""
        if num_train <= 100000:
            obj_func = self.session.run(self.obj_func, feed_dict={self.train_inputs: data.X,
                                                                  self.train_outputs: data.Y,
                                                                  self.num_train: num_train})
            print(f"iter={iter_num!r} [epoch={data.epochs_completed!r}]", end=" ")

            for k in obj_func:
                print(f"obj_func={k}, {obj_func[k]!r}")
