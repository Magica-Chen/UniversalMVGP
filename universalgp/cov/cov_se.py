#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan 23 15:57:59 2018

@author: zc223
"""

import numpy as np
import tensorflow as tf
from .. import util


class SquaredExponential:
    def __init__(self, input_dim, output_dim=1, length_scale=1.0, sf=1.0, iso=False):
        """
        Args:
            iso:
        if iso:
             consider ISO (isotropic) kernel
        else:
             consider ARD (automatic relevance determination) kernel
        """
        self.input_dim = input_dim
        self.num_latent = output_dim
        self.iso = iso
        init_value = tf.constant_initializer(length_scale, dtype=tf.float32)
        with tf.variable_scope("cov_se_parameters"):
            if iso:
                self.length_scale = tf.get_variable("length_scale", [output_dim, input_dim], initializer=init_value)
            else:
                self.length_scale = tf.get_variable("length_scale", [output_dim], initializer=init_value)
            self.sf = tf.get_variable("sf", [output_dim], initializer=tf.constant_initializer(sf, dtype=tf.float32))

    def cov_func(self, point1, point2=None):
        """
        Args:
            point1: Tensor(num_latent, num_inducing, input_dim) or Tensor(batch_size, input_dim)
            point2: Tensor(batch_size, input_dim)
        Returns:
            Tensor of shape (num_latent, num_inducing, batch_size)
        """
        length_scale_br = tf.reshape(self.length_scale, [self.num_latent, 1, 1 if self.iso else self.input_dim])
        if point2 is None:
            point2 = point1

        kern = self.sf[:, tf.newaxis, tf.newaxis]**2 * tf.exp(-util.sq_dist(point1, point2) / 2.0 / length_scale_br**2)
        return kern

    def diag_cov_func(self, points):
        """
        Args:
            points: Tensor(batch_size, input_dim)
        Returns:
            Tensor of shape (num_latent, batch_size)
        """
        return (self.sf**2)[:, tf.newaxis] * tf.ones([tf.shape(points)[-2]])

    def get_params(self):
        return [self.length_scale, self.sf]

    def num_latent_functions(self):
        return self.num_latent
