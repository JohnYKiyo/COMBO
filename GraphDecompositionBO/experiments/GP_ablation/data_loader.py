import os
import numpy as np
import torch

from GraphDecompositionBO.experiments.synthetic_binary import highorder_interaction_function, generate_function_on_highorderbinary
from GraphDecompositionBO.experiments.MaxSAT.maximum_satisfiability import MaxSAT


MAXSAT_DIR_NAME = os.path.join(os.path.split(__file__)[0], '..', 'MaxSAT', 'maxsat2018_data')


def load_highorderbinary(data_type, train_data_scale, random_seed=None):
	assert data_type in [1, 2, 3]
	assert train_data_scale in [1, 2, 3, 4, 5]
	eval_seed, data_seed = np.random.RandomState(random_seed).randint(0, 10000, 2)
	n_variable = 5 * (1 + data_type)
	highest_order = 3 + data_type
	n_data = 250 * 2 ** (data_type - 1)
	n_train = train_data_scale * int(n_data * 0.1)
	input_data = _random_binary_input_data(n_data, n_variable, data_seed)
	interaction_coef = generate_function_on_highorderbinary(n_variable, highest_order, random_seed=eval_seed)
	output_data = torch.from_numpy(highorder_interaction_function(input_data, interaction_coef).astype(np.float32)).unsqueeze(1)
	input_data = torch.from_numpy(input_data)
	train_input = input_data[:n_train]
	train_output = output_data[:n_train]
	test_input = input_data[n_train:]
	test_output = output_data[n_train:]
	return (train_input, train_output), (test_input, test_output)


def _random_binary_input_data(n_data, n_variable, random_seed=None):
	rng_state = np.random.RandomState(random_seed)
	data = rng_state.randint(0, 2, (1, n_variable))
	for _ in range(1, n_data):
		datum = rng_state.randint(0, 2, (1, n_variable))
		while np.sum(np.all(data == datum, axis=1)) > 0:
			datum = rng_state.randint(0, 2, (1, n_variable))
		data = np.vstack([data, datum])
	return data


def load_maxsat(data_type, train_data_scale, random_seed=None):
	if data_type == 1:
		data_filename = 'maxcut-johnson8-2-4.clq.wcnf' # 28 variables
	elif data_type == 2:
		data_filename = 'maxcut-hamming8-2.clq.wcnf' # 43 variables
	elif data_type == 3:
		data_filename = 'frb-frb10-6-4.wcnf' # 60 variables
	data_seed = np.random.RandomState(random_seed).randint(0, 10000)
	n_data = 1000
	n_train = train_data_scale * 50
	maxsat = MaxSAT(os.path.join(MAXSAT_DIR_NAME, data_filename))
	input_data = torch.from_numpy(np.random.RandomState(data_seed).randint(0, 2, [n_data, maxsat.nbvar]))
	output_data = []
	for i in range(n_data):
		output_data.append(maxsat.evaluate(input_data[i]))
	output_data = torch.cat(output_data, dim=0)
	train_input = input_data[:n_train]
	train_output = output_data[:n_train]
	test_input = input_data[n_train:]
	test_output = output_data[n_train:]
	return (train_input, train_output), (test_input, test_output)


if __name__ == '__main__':
	(train_input, train_output), (test_input, test_output) = load_maxsat(1, 1, 1)
	print(train_output)
