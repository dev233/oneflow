"""
Copyright 2020 The OneFlow Authors. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import oneflow as flow
import oneflow.typing as tp

from collections import OrderedDict
import numpy as np
import os
from test_util import GenArgList
import unittest


def _compare_instance_norm_2d_with_np(
    input_shape, device_type, machine_ids, device_counts, eps, affine
):
    assert device_type in ["cpu", "gpu"]
    assert len(input_shape) == 4

    flow.clear_default_session()

    if device_type == "cpu":
        flow.config.cpu_device_num(device_counts)
    else:
        flow.config.gpu_device_num(device_counts)

    func_config = flow.FunctionConfig()
    func_config.default_placement_scope(flow.scope.placement(device_type, machine_ids))

    input = np.random.random(size=input_shape).astype(np.float32)
    gout = np.random.random(size=input_shape).astype(np.float32)

    # compute instance normalization in numpy
    gamma = np.ones((1, input_shape[1], 1, 1), dtype=np.float32)
    mean_np = np.mean(input, axis=(2, 3), keepdims=True)
    in_sub_mean = input - mean_np
    var_np = np.mean(np.square(in_sub_mean), axis=(2, 3), keepdims=True)
    invar_np = 1.0 / np.sqrt(var_np + eps)
    out_np = in_sub_mean * invar_np * gamma

    def assert_prediction_grad(gin_of: tp.Numpy):
        # compute the gradient of variance
        gvar = gout * gamma * in_sub_mean * -0.5 * np.power(var_np + eps, -1.5)
        gvar = np.sum(gvar, axis=(2, 3), keepdims=True)
        # compute the gradient of mean
        gmean = np.sum(gout * gamma, axis=(2, 3), keepdims=True)
        gmean *= -invar_np
        scale = 1.0 / (input_shape[2] * input_shape[3])
        tmp = scale * np.sum(-2.0 * in_sub_mean, axis=(2, 3), keepdims=True) * gvar
        gmean += tmp
        # compute the gradient of input
        gin_np = (
            gout * gamma * invar_np + gvar * scale * 2.0 * in_sub_mean + gmean * scale
        )

        assert np.allclose(gin_of, gin_np, atol=1e-5)

    @flow.global_function(type="train", function_config=func_config)
    def instanceNormJob(
        of_input: tp.Numpy.Placeholder(shape=input.shape),
        multipler: tp.Numpy.Placeholder(shape=input.shape),
    ) -> tp.Numpy:
        with flow.scope.placement(device_type, "0:0"):
            v = flow.get_variable(
                shape=of_input.shape,
                dtype=flow.float32,
                initializer=flow.constant_initializer(0),
                name="v",
            )

            x_var = of_input + v
            # watch the gradient
            flow.watch_diff(x_var, assert_prediction_grad)

        out = flow.nn.InstanceNorm2d(x_var, eps=eps, affine=affine)

        with flow.scope.placement(device_type, "0:0"):
            flow.optimizer.SGD(
                flow.optimizer.PiecewiseConstantScheduler([], [1e-3]), momentum=0
            ).minimize(out * multipler)

        return out

    check = flow.train.CheckPoint()
    check.init()

    of_out = instanceNormJob(input, gout)

    assert np.allclose(of_out, out_np, atol=1e-5)


@flow.unittest.skip_unless_1n1d()
class TestInstanceNorm1n1d(flow.unittest.TestCase):
    def test_instance_norm(test_case):
        arg_dict = OrderedDict()
        arg_dict["input_shape"] = [(4, 2, 32, 32)]
        arg_dict["device_type"] = ["cpu", "gpu"]
        arg_dict["machine_ids"] = ["0:0"]
        arg_dict["device_counts"] = [1]
        arg_dict["eps"] = [1e-3]
        arg_dict["affine"] = [True, False]
        for arg in GenArgList(arg_dict):
            _compare_instance_norm_2d_with_np(*arg)


@flow.unittest.skip_unless_1n2d()
class TestInstanceNorm1n2d(flow.unittest.TestCase):
    def test_instance_norm(test_case):
        arg_dict = OrderedDict()
        arg_dict["input_shape"] = [(4, 2, 32, 32)]
        arg_dict["device_type"] = ["cpu", "gpu"]
        arg_dict["machine_ids"] = ["0:0-1"]
        arg_dict["device_counts"] = [2]
        arg_dict["eps"] = [1e-3]
        arg_dict["affine"] = [True, False]
        for arg in GenArgList(arg_dict):
            _compare_instance_norm_2d_with_np(*arg)


if __name__ == "__main__":
    unittest.main()
