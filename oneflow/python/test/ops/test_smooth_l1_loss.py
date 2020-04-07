import oneflow as flow
import numpy as np
from collections import OrderedDict
import uuid
from test_util import GenArgList
from test_util import type_name_to_flow_type
from test_util import type_name_to_np_type

def gen_numpy_data(prediction, label, beta=1.0):
    original_shape = prediction.shape
    elem_cnt = prediction.size
    prediction = prediction.reshape(-1)
    label = label.reshape(-1)
    loss = np.zeros((elem_cnt)).astype(prediction.dtype)
    prediction_grad = np.zeros((elem_cnt)).astype(prediction.dtype)

    # Forward
    for i in np.arange(elem_cnt):
        abs_diff = abs(prediction[i] - label[i])
        if abs_diff < beta:
            loss[i] = 0.5 * abs_diff * abs_diff / beta
        else:
            loss[i] = abs_diff - 0.5 * beta

    # Backward
    for i in np.arange(elem_cnt):
        diff = prediction[i] - label[i]
        abs_diff = abs(diff)
        if abs_diff < beta:
            prediction_grad[i] = diff / beta
        else:
            prediction_grad[i] = np.sign(diff)
    
    return {
        "loss": loss.reshape(original_shape),
        "prediction_grad": prediction_grad.reshape(original_shape)
    }

def test_smooth_l1_loss(_):
    arg_dict = OrderedDict()
    arg_dict["device_type"] = ["gpu", "cpu"]
    arg_dict["prediction_shape"] = [
        (100,),
        (10, 10),
    ]
    arg_dict["data_type"] = ["float32", "double"]
    arg_dict["beta"] = [0, 0.5, 1]

    for case in GenArgList(arg_dict):
        device_type, prediction_shape, data_type, beta = case
        assert device_type in ["gpu", "cpu"]
        assert data_type in ["float32", "double", "int8", "int32", "int64"]
        flow.clear_default_session()
        func_config = flow.FunctionConfig()
        func_config.default_data_type(flow.float)
        func_config.train.primary_lr(1e-4)
        func_config.train.model_update_conf(dict(naive_conf={}))

        prediction = np.random.randn(*prediction_shape).astype(type_name_to_np_type[data_type])
        label = np.random.randn(*prediction_shape).astype(type_name_to_np_type[data_type])

        np_result = gen_numpy_data(prediction, label, beta)

        def assert_prediction_grad(b):
            prediction_grad = np_result["prediction_grad"]
            assert prediction_grad.dtype == type_name_to_np_type[data_type]
            assert np.allclose(prediction_grad, b.ndarray()), (case, prediction_grad, b.ndarray())

        @flow.function(func_config)
        def TestJob(
            prediction=flow.FixedTensorDef(prediction_shape, dtype=type_name_to_flow_type[data_type]),
            label=flow.FixedTensorDef(prediction_shape, dtype=type_name_to_flow_type[data_type])
        ):
            v = flow.get_variable(
                "prediction",
                shape=prediction_shape,
                dtype=type_name_to_flow_type[data_type],
                initializer=flow.constant_initializer(0),
                trainable=True,
            )
            flow.watch_diff(v, assert_prediction_grad)
            prediction += v
            with flow.fixed_placement(device_type, "0:0"):
                loss = flow.smooth_l1_loss(prediction, label, beta)
                flow.losses.add_loss(loss)
                return loss
        
        loss_np = np_result["loss"]
        assert loss_np.dtype == type_name_to_np_type[data_type]
        loss = TestJob(prediction, label).get().ndarray()
        assert np.allclose(loss_np, loss), (case, loss_np, loss)